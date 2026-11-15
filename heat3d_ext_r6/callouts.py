"""
Where each player is, in the map's own words: the room callouts ("2F CCTV
Room", "EXT Parking") the game shows above the minimap.

The event section sets a location field on small per-player objects,

    23 <object:u32> 00 00 00 00  af 98 99 ca  08 ff*8
    26 af 98 99 ca 00 00 00 00 <len:u8> <callout>

each time the pawn it follows walks into another room (an empty string
outside every named room). The field is the one a player's block in the
snapshot carries as the spawn ("Main Gate"). Each player has two such
objects: one follows the operator's body; the other an attacker's drone in
the preparation phase, or what a defender is watching. Which object follows
which pawn is not written down: it is told by movement - the object's
callout changes where one of the player's tracks moves - and the object
belongs to the player in whose block of the snapshot it first stands.

A site is named the same way: "B Church, B Arsenal Room" is two callouts.

Worked out here from the files.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from .rec import Rec

FIELD = b"\xaf\x98\x99\xca"
SET = re.compile(rb"\x23(....)\x00\x00\x00\x00\xaf\x98\x99\xca", re.S)
VALUE = b"\x26\xaf\x98\x99\xca\x00\x00\x00\x00"
NAME = b"\x22\x07\x94\x9b\xdc"


@dataclass
class Timeline:
    """One object's callouts: (tick, callout) as set, in tick order."""
    ticks: list[int] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

    def at(self, tick: int) -> str:
        i = bisect.bisect_right(self.ticks, tick) - 1
        return self.names[i] if i >= 0 else ""


def _sets(rec: Rec) -> dict[bytes, Timeline]:
    b = rec.body
    out: dict[bytes, Timeline] = {}
    for m in SET.finditer(b, rec.snapshot_end):
        k = b.find(VALUE, m.end(), m.end() + 40)
        if k < 0:
            continue
        n = b[k + 9] if k + 9 < len(b) else 0
        name = b[k + 10 : k + 10 + n].decode("utf-8", "replace")
        tick = rec.tick_at(m.start())
        if tick is None:
            continue
        tl = out.setdefault(m.group(1), Timeline())
        if tl.ticks and tick < tl.ticks[-1]:
            continue
        if tl.names and tl.names[-1] == name:
            continue
        tl.ticks.append(tick)
        tl.names.append(name.replace("<br/>", ", "))
    return out


def _owners(rec: Rec, objs: list[bytes], names: list[str]) -> dict[bytes, str]:
    """Each object's player: whose block of the snapshot holds its first mention."""
    b = rec.body
    end = rec.snapshot_end
    starts = sorted((m.start(), b[m.start() + 6 : m.start() + 6 + b[m.start() + 5]].decode("utf-8", "replace"))
                    for m in re.finditer(re.escape(NAME), b[:end]))
    known = set(names)
    out: dict[bytes, str] = {}
    for obj in objs:
        p = b.find(obj, starts[0][0] if starts else 0, end)
        if p < 0:
            continue
        i = bisect.bisect_right([s for s, _ in starts], p) - 1
        if i >= 0 and starts[i][1] in known:
            out[obj] = starts[i][1]
    return out


def _moved(ticks: list[int], track: list, t: int) -> bool:
    i = bisect.bisect_left(ticks, t - 4)
    j = bisect.bisect_right(ticks, t + 4)
    if j - i < 2:
        return False
    a, c = track[i], track[j - 1]
    return abs(a[1] - c[1]) + abs(a[2] - c[2]) + abs(a[3] - c[3]) > 0.05


def read(rec: Rec, players, tracks: dict[int, list]) -> dict[int, Timeline]:
    """
    The callouts of each followed pawn, by its object in the object stream
    (the keys of `tracks`): the body's, and a drone's where one is told.
    """
    sets = _sets(rec)
    if not sets:
        return {}
    owners = _owners(rec, list(sets), [p.name for p in players])
    by_name = {p.name: p for p in players}
    out: dict[int, Timeline] = {}
    for name in {o for o in owners.values()}:
        pl = by_name[name]
        mine = [obj for obj, n in owners.items() if n == name]
        cands = [(o, k) for o, k in pl.objects.items() if k in ("operator", "drone") and tracks.get(o)]
        scores = []
        for obj in mine:
            tl = sets[obj]
            changes = [t for t, s, s0 in zip(tl.ticks[1:], tl.names[1:], tl.names) if s and s != s0]
            if len(changes) < 2:
                continue
            for o, kind in cands:
                tr = tracks[o]
                ticks = [s[0] for s in tr]
                score = sum(_moved(ticks, tr, t) for t in changes) / len(changes)
                scores.append((score, len(changes), obj, o, kind))
        scores.sort(reverse=True)
        used_obj: set[bytes] = set()
        used_track: set[int] = set()
        for score, _n, obj, o, kind in scores:
            if score < 0.5 or obj in used_obj or o in used_track:
                continue
            used_obj.add(obj)
            used_track.add(o)
            out[o] = sets[obj]
        # A body never matched by movement (a player who stood still): the object whose callouts start with
        # the body's track, if one is left.
        body = [o for o, k in cands if k == "operator" and o not in out]
        rest = [obj for obj in mine if obj not in used_obj and sets[obj].names and any(sets[obj].names)]
        if body and len(rest) == 1 and not any(k == "drone" for _o, k in cands if _o not in out):
            out[body[0]] = sets[rest[0]]
    return out


def at(timelines: dict[int, Timeline], obj: int | None, tick: int) -> str:
    tl = timelines.get(obj) if obj is not None else None
    return tl.at(tick) if tl else ""


def rooms(site: str | None) -> list[str]:
    """A site's callouts: "B Church, B Arsenal Room" -> ["B Church", "B Arsenal Room"]."""
    return [s.strip() for s in (site or "").replace("<br/>", ",").split(",") if s.strip()]
