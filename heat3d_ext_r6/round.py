"""
One round read: the players, where each was tick by tick, the round clock,
the kill feed, the defuser and the result.

Who is who. Each player's block in the snapshot region carries the name, the
operator, a 4-byte id the events use and the 64-bit player id; the pawn table
pairs that player id with the objects the player drives,

    <player id:u64> <1-5 bytes> 0xff <object:u32>

an operator's body (`39 02 <slot> 01 ff` on defence, `21 02 ff` on attack)
and, for attackers in the preparation phase, a drone (`f9 00 <slot> 00 ff`).
Every object whose packets carry a position (flag 0x80 in the fifth byte:
x, y, z as float32 at byte 6, metres, Z up) is followed; the ones the table
names become the players' tracks, the rest are kept as objects.

Time. Blocks are ticks, not seconds: the server ticks at about 29-40 per
second and not evenly. The round clock (`1f 07 ef c9`, seconds, with the
milliseconds left under `22 18 37 46 6c 04`) stands in the event section at
its tick; seconds are put on every tick by following that clock, and where it
jumps up (preparation to action, the end) by the tick rate around the jump.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field

from . import game
from .rec import Rec, packets

NAME = b"\x22\x07\x94\x9b\xdc"
OPERATOR = b"\x40\xf2\x15\x04"
DISSECT_ID = b"\x33\xd8\x3d\x4f\x23"
DISSECT_ID_OLD = b"\xe6\xf9\x7d\x86"
PLAYER_ID = b"\xee\xd4\x45\xc8\x08"
SPAWN = b"\xaf\x98\x99\xca"
CLOCK = b"\x1f\x07\xef\xc9"
CLOCK_OLD = b"\x1e\xf1\x11\xab"
CLOCK_MS = b"\x22\x18\x37\x46\x6c\x04"
FEED = b"\x59\x34\xe5\x8b\x04"
KILL = b"\x22\xd9\x13\x3c\xba"
FEED_OLD = b"\x00\x00\x00\x22\xe3\x09\x00\x79"
DEFUSER = b"\x22\xa9\xc8\x58\xd9"
SITE_CURRENT = b"\xfc\xc6\xa8\x60\x01"
POSITION_FLAG = 0x80


@dataclass
class Player:
    name: str
    team: int
    operator: str | None = None
    operator_id: int | None = None
    event_id: bytes = b""
    player_id: int | None = None
    spawn: str | None = None
    objects: dict[int, str] = field(default_factory=dict)  # object -> "operator" | "drone" | "linked"


@dataclass
class Event:
    kind: str
    tick: int | None
    clock: float | None
    player: str | None = None
    other: str | None = None
    headshot: bool | None = None
    text: str | None = None


@dataclass
class Round:
    rec: Rec
    number: int
    map: str | None
    mode: str | None
    version: str | None
    players: list[Player]
    tracks: dict[int, list[tuple[int, float, float, float, float, int, int]]]  # object -> (tick, x, y, z, yaw, flags, bytes)
    anchors: list[tuple[int, int, float]]  # tick, phase, seconds left
    events: list[Event]
    site: str | None
    roles: dict[int, str]
    winner: int | None
    win_condition: str | None
    action_tick: int | None
    tick_seconds: list[tuple[int, float]] = field(default_factory=list)
    phase_names: list[str] = field(default_factory=list)

    def owner(self, obj: int) -> Player | None:
        for p in self.players:
            if obj in p.objects:
                return p
        return None

    def seconds(self, tick: int | None) -> float | None:
        """Seconds since the recording's first tick."""
        if tick is None or not self.tick_seconds:
            return None
        ts = self.tick_seconds
        if tick <= ts[0][0]:
            return max(0.0, ts[0][1] - (ts[0][0] - tick) * _rate(ts, 0))
        if tick >= ts[-1][0]:
            return ts[-1][1] + (tick - ts[-1][0]) * _rate(ts, len(ts) - 2)
        lo, hi = 0, len(ts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ts[mid][0] <= tick:
                lo = mid
            else:
                hi = mid
        (t0, s0), (t1, s1) = ts[lo], ts[hi]
        return s0 + (s1 - s0) * (tick - t0) / (t1 - t0)

    def phase(self, tick: int | None) -> str | None:
        if tick is None or not self.anchors:
            return None
        ph = self.anchors[0][1]
        for t, p, _ in self.anchors:
            if t > tick:
                break
            ph = p
        return self.phase_names[ph] if ph < len(self.phase_names) else f"phase {ph + 1}"


def _rate(ts: list[tuple[int, float]], i: int) -> float:
    i = max(0, min(i, len(ts) - 2))
    if len(ts) < 2:
        return 1 / 30
    dt = ts[i + 1][0] - ts[i][0]
    return (ts[i + 1][1] - ts[i][1]) / dt if dt else 1 / 30


def _string(b: bytes, p: int) -> tuple[str, int]:
    n = b[p]
    return b[p + 1 : p + 1 + n].decode("utf-8", "replace"), p + 1 + n


def _players(rec: Rec) -> list[Player]:
    body = rec.body
    region_end = rec.snapshot_end or len(body)
    code = rec.code()
    teams = {h.get("playername"): int(h["team"]) for h in rec.header_players if h.get("team", "").isdigit()}
    found: dict[str, Player] = {}
    order: list[str] = []
    starts = [m.start() for m in re.finditer(re.escape(NAME), body[:region_end])]
    for i, p in enumerate(starts):
        try:
            name, q = _string(body, p + 5)
        except IndexError:
            continue
        if not name:
            continue
        stop = starts[i + 1] if i + 1 < len(starts) else min(region_end, p + 8000)
        win = body[q:stop]
        pl = found.get(name)
        if pl is None:
            order.append(name)
            pl = found[name] = Player(name, teams.get(name, 0 if len(order) <= 5 else 1))
        k = win.find(OPERATOR)
        if k >= 0 and k + 22 <= len(win) and win[k + 12] != 0x9D:
            op = struct.unpack_from("<Q", win, k + 14)[0]
            if op and win[k + 22 : k + 23] in (b"\x22", b""):
                pl.operator_id = op
                pl.operator = game.operator_name(op)
        k = win.find(DISSECT_ID if code > game.Y7S2 else DISSECT_ID_OLD)
        if k >= 0 and not pl.event_id:
            pl.event_id = win[k + 5 : k + 9] if code > game.Y7S2 else win[k + 4 : k + 8]
        k = win.find(SPAWN)
        if k >= 0 and pl.spawn is None:
            s, _ = _string(win, k + 4)
            pl.spawn = s.replace("<br/>", ", ") or None
        k = win.find(PLAYER_ID)
        if k >= 0 and pl.player_id is None and k + 13 <= len(win):
            pl.player_id = struct.unpack_from("<Q", win, k + 5)[0]
    # Header ids where the blocks gave none (the header lists the recording team's players).
    for h in rec.header_players:
        pl = found.get(h.get("playername", ""))
        if pl and pl.player_id is None and h.get("playerid", "").isdigit():
            pl.player_id = int(h["playerid"])
    return [found[n] for n in order]


def _link(rec: Rec, players: list[Player], tracks: dict[int, list]) -> None:
    """
    Each object's full update (the one that creates it) carries its owner's
    64-bit player id: the operator's body, drones, thrown and placed gadgets.
    Every object that moves and names a player is that player's; the kind is
    told by its packets' size (a body's update is over 800 bytes, a drone's
    a few hundred and many, a gadget's small).
    """
    body = rec.body
    blocks = [b for b in rec.blocks if b.section == 0]
    starts = [b.start for b in blocks]
    import bisect

    for pl in players:
        if pl.player_id is None:
            continue
        key = struct.pack("<Q", pl.player_id)
        for sec in rec.sections[:1]:
            p = body.find(key, sec.start, sec.end)
            while p != -1:
                i = bisect.bisect_right(starts, p) - 1
                if i >= 0 and p < blocks[i].end:
                    for obj, _aux, q, size in packets(rec, blocks[i]):
                        if q <= p < q + size:
                            if obj in tracks and obj not in pl.objects:
                                big = max(t[6] for t in tracks[obj])
                                pl.objects[obj] = "operator" if big >= 800 else (
                                    "drone" if big >= 150 and len(tracks[obj]) > 100 else "gadget")
                            break
                p = body.find(key, p + 1, sec.end)
    # A player with no body found that way: the pawn table of the snapshot region.
    head = body[: rec.snapshot_end]
    for pl in players:
        if pl.player_id is None or any(k == "operator" for k in pl.objects.values()):
            continue
        key = struct.pack("<Q", pl.player_id)
        p = head.find(key)
        while p != -1:
            e = p + 8
            for j in range(1, 6):
                if head[e + j - 1 : e + j] == b"\xff" and head[e + j + 3 : e + j + 4] == b"\xf0":
                    obj = struct.unpack_from("<I", head, e + j)[0]
                    if obj in tracks and head[e + 1 : e + 2] == b"\x02":
                        pl.objects[obj] = "operator"
                    break
            p = head.find(key, p + 1)


def _tracks(rec: Rec) -> dict[int, list[tuple[int, float, float, float, float, int]]]:
    out: dict[int, list] = {}
    body = rec.body
    unpack = struct.unpack_from
    for blk in rec.blocks:
        if blk.section != 0:
            continue
        for obj, _aux, q, size in packets(rec, blk):
            if size < 18 or body[q + 1 : q + 4] != b"\x73\x85\xfe" or not body[q + 4] & POSITION_FLAG:
                continue
            x, y, z = unpack("<3f", body, q + 6)
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)) or max(abs(x), abs(y), abs(z)) > 5000:
                continue
            yaw = float("nan")
            if size >= 38:
                qz, qw = unpack("<2f", body, q + 30)
                a, b = unpack("<2f", body, q + 22)
                if abs(math.hypot(qz, qw) - 1) < 0.02 and abs(a) < 0.05 and abs(b) < 0.05:
                    yaw = math.degrees(2 * math.atan2(qz, qw))
            out.setdefault(obj, []).append((blk.tick, x, y, z, yaw, body[q + 4], size))
    return out


def _anchors(rec: Rec) -> list[tuple[int, int, float]]:
    """(tick, phase, seconds left) at each clock packet; the phase counts the clock's jumps up."""
    body = rec.body
    raw: list[tuple[int, float]] = []
    start = rec.snapshot_end
    if rec.code() >= game.Y8S1:
        p = body.find(CLOCK, start)
        while p != -1:
            t = rec.tick_at(p)
            if t is not None and p + 9 <= len(body):
                sec = struct.unpack_from("<I", body, p + 5)[0]
                k = body.find(CLOCK_MS, p + 9, p + 40)
                left = struct.unpack_from("<I", body, k + 6)[0] / 1000 if k >= 0 else float(sec)
                if sec < 100000 and (k < 0 or abs(left - sec) < 2):
                    raw.append((t, left))
            p = body.find(CLOCK, p + 4)
    raw.sort()
    out: list[tuple[int, int, float]] = []
    phase = 0
    for t, left in raw:
        if out and left > out[-1][2] + 1.5:
            phase += 1
        if out and out[-1][0] == t:
            continue
        out.append((t, phase, left))
    return out


def _tick_seconds(anchors: list[tuple[int, int, float]]) -> list[tuple[int, float]]:
    if len(anchors) < 2:
        return []
    pairs = list(zip(anchors, anchors[1:]))

    def steady(a, b) -> bool:  # the clock running: same phase, about a second a step, a few ticks apart
        return a[1] == b[1] and 0.5 < a[2] - b[2] < 1.5 and b[0] > a[0]

    def rate_near(i: int) -> float:
        near = sorted(((a[2] - b[2]) / (b[0] - a[0]) for a, b in pairs[max(0, i - 8): i + 8] if steady(a, b)))
        if not near:
            near = sorted((a[2] - b[2]) / (b[0] - a[0]) for a, b in pairs if steady(a, b)) or [1 / 30]
        return near[len(near) // 2]

    out = [(anchors[0][0], 0.0)]
    for i, (a, b) in enumerate(pairs):
        if steady(a, b) or (a[1] == b[1] and 0 <= a[2] - b[2] <= 0.5 and b[0] > a[0]):
            out.append((b[0], out[-1][1] + (a[2] - b[2])))
        else:  # a jump (phase change, the clock stopped or set to zero): the ticks at the rate around it
            out.append((b[0], out[-1][1] + (b[0] - a[0]) * rate_near(i)))
    # Shift so the recording's first tick (1) is 0 s.
    first = out[0][1] - (out[0][0] - 1) * _rate(out, 0)
    return [(t, s - first) for t, s in out]


def _feed(rec: Rec, by_event_id: dict[bytes, Player]) -> tuple[list[Event], str | None]:
    body = rec.body
    code = rec.code()
    start = rec.snapshot_end
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()

    # The clock as last seen in stream order, for events outside any block (old files).
    clocks = []
    p = body.find(CLOCK, start)
    while p != -1:
        clocks.append((p, struct.unpack_from("<I", body, p + 5)[0]))
        p = body.find(CLOCK, p + 4)

    def clock_at(off: int) -> float | None:
        c = None
        for o, v in clocks:
            if o > off:
                break
            c = v
        return c

    p = body.find(FEED, start)
    while p != -1:
        q = p + 5
        ok = True
        if code >= game.Y9S1_UPDATE3:
            q += 38
        elif code >= game.Y9S1:
            q += 9
            ok = body[q] == 4
            q += 25
        else:
            k = body.find(FEED_OLD, q + 1, q + 4000)
            ok = k >= 0
            q = k + len(FEED_OLD)
        if ok and q < len(body):
            size = body[q]
            q += 1
            tick = rec.tick_at(p)
            if size == 0 and body[q : q + 5] == KILL:
                killer, q = _string(body, q + 5)
                target, q = _string(body, q + 15)
                if not killer and target:
                    events.append(Event("death", tick, clock_at(p), player=target))
                elif killer and (killer, target) not in seen:
                    seen.add((killer, target))
                    hs = body[q + 56] == 1 if q + 56 < len(body) else None
                    events.append(Event("kill", tick, clock_at(p), player=killer, other=target, headshot=hs))
            elif size and code < game.Y9S1:
                msg = body[q : q + size].decode("utf-8", "replace")
                kind = "battleye" if "BattlEye" in msg else "leave" if "left" in msg else \
                    "locate" if ("bombs" in msg or "objective" in msg) else "message"
                events.append(Event(kind, tick, clock_at(p), player=msg.split(" ")[0] if kind != "message" else None,
                                    text=msg))
        p = body.find(FEED, p + 5)

    planted = False
    last: Player | None = None
    p = body.find(DEFUSER, start)
    while p != -1:
        timer, q = _string(body, p + 5)
        pid = body[q + 34 : q + 38]
        pl = by_event_id.get(pid)
        tick = rec.tick_at(p)
        if pl is not None:
            events.append(Event("defuse_start" if planted else "plant_start", tick, clock_at(p), player=pl.name,
                                text=timer))
            last = pl
        if timer.startswith("0.00") and last is not None:
            events.append(Event("defuse" if planted else "plant", tick, clock_at(p), player=last.name))
            planted = True
        p = body.find(DEFUSER, p + 5)

    site = None
    p = body.find(SPAWN)
    while p != -1:
        loc, q = _string(body, p + 4)
        if "<br/>" in loc:
            if site is None or body[q + 150 : q + 155] == SITE_CURRENT:
                site = loc.replace("<br/>", ", ")
        p = body.find(SPAWN, p + 4)
    events.sort(key=lambda e: (e.tick if e.tick is not None else 1 << 40))
    return events, site


def read_round(rec: Rec) -> Round:
    h = rec.header
    tracks = _tracks(rec)
    players = _players(rec)
    _link(rec, players, tracks)
    anchors = _anchors(rec)
    events, site = _feed(rec, {p.event_id: p for p in players if p.event_id})
    # The phases by the clock they start with: the action phase starts near 3:00 (the longest),
    # the preparation is the one before it, what follows is after the plant or the round's end.
    first_left: dict[int, float] = {}
    first_tick: dict[int, int] = {}
    for t, p, left in anchors:
        first_left.setdefault(p, left)
        first_tick.setdefault(p, t)
    action = max(first_left, key=lambda p: first_left[p]) if first_left else None
    plant_tick = next((e.tick for e in events if e.kind == "plant" and e.tick is not None), None)
    names = []
    for p in range(max(first_left, default=-1) + 1):
        if p == action:
            names.append("action")
        elif action is not None and p < action:
            names.append("prep")
        elif plant_tick is not None and first_tick.get(p, 0) >= plant_tick - 60:
            names.append("planted")
        else:
            names.append("end")
    action_tick = first_tick.get(action) if action is not None else None

    # Sides: by the operators each team picked (most of them).
    roles: dict[int, str] = {}
    for team in (0, 1):
        votes = [game.side_of(p.operator) for p in players if p.team == team]
        a, d = votes.count("attack"), votes.count("defense")
        if a != d:
            roles[team] = "attack" if a > d else "defense"
    if len(roles) == 1:
        (t, r), = roles.items()
        roles[1 - t] = "defense" if r == "attack" else "attack"
    if any(e.kind == "plant" for e in events) and not roles:
        planter = next(e.player for e in events if e.kind == "plant")
        t = next((p.team for p in players if p.name == planter), None)
        if t is not None:
            roles = {t: "attack", 1 - t: "defense"}

    winner = None
    try:
        s0, s1 = int(h.get("teamscore0", "")), int(h.get("teamscore1", ""))
        b0, b1 = int(h.get("startingteamscore0", "-1")), int(h.get("startingteamscore1", "-1"))
        if b0 >= 0 and b1 >= 0:
            winner = 0 if s0 > b0 else 1 if s1 > b1 else None
    except ValueError:
        pass
    condition = None
    kinds = [e.kind for e in events]
    team_of = {p.name: p.team for p in players}
    dead = {t: 0 for t in (0, 1)}
    for e in events:
        victim = e.other if e.kind == "kill" else e.player if e.kind == "death" else None
        if victim in team_of:
            dead[team_of[victim]] += 1
    size = {t: sum(1 for p in players if p.team == t) for t in (0, 1)}
    if "defuse" in kinds:
        condition = "defuser disabled"
        w = team_of.get(next(e.player for e in events if e.kind == "defuse"))
        winner = w if winner is None else winner
    elif "plant" in kinds:
        condition = "defuser planted" if winner is None or roles.get(winner) == "attack" else "eliminated after plant"
        if winner is None:
            winner = team_of.get(next(e.player for e in events if e.kind == "plant"))
    elif winner is not None:
        loser = 1 - winner
        condition = "eliminated" if size[loser] and dead[loser] >= size[loser] else \
            "time" if roles.get(winner) == "defense" else "eliminated"
    else:
        for t in (0, 1):
            if size[t] and dead[t] >= size[t]:
                winner, condition = 1 - t, "eliminated"
        if winner is None and roles:
            winner = next(t for t, r in roles.items() if r == "defense")
            condition = "time"

    try:
        number = int(h.get("roundnumber", "0")) + 1
    except ValueError:
        number = 0
    try:
        mode = game.MODES.get(int(h.get("gamemodeid", "0")))
    except ValueError:
        mode = None
    r = Round(rec, number, game.map_name(h.get("worldid")), mode, h.get("version"), players, tracks, anchors,
              events, site, roles, winner, condition, action_tick)
    r.tick_seconds = _tick_seconds(anchors)
    r.phase_names = names
    return r
