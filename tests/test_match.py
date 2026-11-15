"""Callouts, plant and defuse attempts, bomb sites and mark attribution on synthetic data."""

from __future__ import annotations

import math
import struct

from heat3d_ext_r6 import callouts, impacts, sites
from heat3d_ext_r6.round import Player, TimerPacket, _attempts


def _loc(obj: int, name: str) -> bytes:
    s = name.encode()
    return (b"\x23" + struct.pack("<I", obj) + b"\x00" * 4 + callouts.FIELD + b"\x08" + b"\xff" * 8
            + callouts.VALUE + bytes([len(s)]) + s)


class _Rec:
    """Just enough of a Rec: a body, a snapshot end and a tick per offset."""

    def __init__(self, snapshot: bytes, ticks: list[tuple[int, bytes]]):
        self.body = snapshot
        self.snapshot_end = len(snapshot)
        self._at: list[tuple[int, int, int]] = []
        for tick, data in ticks:
            self._at.append((len(self.body), len(self.body) + len(data), tick))
            self.body += data

    def tick_at(self, off: int):
        for a, b, t in self._at:
            if a <= off < b:
                return t
        return None


def _snapshot(players: list[tuple[str, list[int]]]) -> bytes:
    out = b""
    for name, objs in players:
        n = name.encode()
        out += callouts.NAME + bytes([len(n)]) + n + b"\x00" * 8
        for o in objs:
            out += b"\x1a\x9d\xeb\xe8\xa7" + struct.pack("<I", o) + b"\x00" * 8
    return out


def test_callouts_follow_the_body():
    snap = _snapshot([("alpha", [0xF01600AA, 0xF01600AB])])
    ticks = [(1, _loc(0xF01600AA, "EXT Parking") + _loc(0xF01600AB, ""))]
    # The body walks from room to room at ticks 10, 20, 30; the other object follows nothing that moves.
    ticks += [(10, _loc(0xF01600AA, "1F Lobby")), (20, _loc(0xF01600AA, "1F Bar")), (30, _loc(0xF01600AA, "1F Stage")),
              (15, _loc(0xF01600AB, "2F Gym")), (25, _loc(0xF01600AB, "B Church")), (35, _loc(0xF01600AB, "2F Gym"))]
    ticks.sort()
    rec = _Rec(snap, ticks)
    # Standing still around the other object's changes, walking around the body's.
    track = [(t, min(t, 11) * 0.5 + max(0, t - 19) * 0.5, 0.0, 0.0, 0.0, 0x80, 900) for t in range(1, 40)]
    pl = Player("alpha", 0, objects={7: "operator"})
    tl = callouts.read(rec, [pl], {7: track})
    assert set(tl) == {7}
    assert tl[7].at(5) == "EXT Parking"
    assert tl[7].at(22) == "1F Bar"
    assert callouts.rooms("B Church<br/>B Arsenal Room") == ["B Church", "B Arsenal Room"]


def _track(x: float, y: float, ticks: range, moving: bool = False):
    return [(t, x + (t * 0.1 if moving else 0.0), y, 0.0, 0.0, 0x80, 900) for t in ticks]


def test_attempts_interrupted_and_done():
    att = Player("att", 0, objects={1: "operator"})
    mover = Player("mover", 0, objects={2: "operator"})
    dfn = Player("dfn", 1, objects={3: "operator"})
    tracks = {1: _track(5, 5, range(0, 600)), 2: _track(0, 0, range(0, 600), moving=True),
              3: _track(6, 5, range(0, 600))}
    timers = [TimerPacket(100 + 2 * i, round(7.0 - 0.068 * i, 3), None, None) for i in range(30)]  # stops at 5.03
    timers += [TimerPacket(200 + 2 * i, max(0.0, round(7.0 - 0.068 * i, 3)), None, None) for i in range(104)]
    timers += [TimerPacket(420 + 2 * i, round(7.0 - 0.068 * i, 3), None, None) for i in range(20)]
    ev = _attempts(timers, [att, mover, dfn], tracks, {0: "attack", 1: "defense"}, {}, "B Church, B Arsenal Room", [])
    kinds = [(e.kind, e.player, e.inferred) for e in ev]
    assert kinds == [("plant_start", "att", True), ("plant_interrupted", "att", True),
                     ("plant_start", "att", True), ("plant", "att", True),
                     ("defuse_start", "dfn", True), ("defuse_interrupted", "dfn", True)]
    assert math.isclose(ev[1].left, 5.028, abs_tol=0.01) and ev[1].of == 7.0


def test_attempts_named_in_the_packet():
    p = Player("named", 0, objects={})
    timers = [TimerPacket(10, 7.0, "named", None), TimerPacket(12, 6.9, None, None)]
    ev = _attempts(timers, [p], {}, {0: "attack"}, {}, None, [])
    assert [(e.kind, e.player, e.inferred) for e in ev] == [("plant_start", "named", False),
                                                            ("plant_interrupted", "named", False)]


def test_room_outline_and_sites():
    pts = [(x * 0.5, y * 0.5, 0.4) for x in range(10) for y in range(8)] + [(40.0, 40.0, 0.4)]
    shape = sites.room_shape(pts)
    assert shape is not None
    xs = [p[0] for p in shape["points"]]
    assert max(xs) <= 4.5 and min(xs) >= 0.0  # the stray far point is dropped
    assert shape["points"][0][2] == 0.4
    objs = sites.objectives(None, [("B Church, B Arsenal Room", 1, 0.0, 100.0), ("B Church, B Arsenal Room", 3, 300.0, 400.0)],
                            {"B Church": pts})
    assert [(o["name"], o["shape"], o["rounds"]) for o in objs] == [("B Church", "outline", [1, 3])]
    assert objs[0]["active"] == [[0.0, 100.0], [300.0, 400.0]]
    assert objs[0]["type"] == "bomb_site" and objs[0]["site"] == "B Church, B Arsenal Room"


def test_mark_attribution():
    mark = impacts.Impact(50, 1, 2, 10.0, 0.2, 1.2, -1, 0, 0, 1.0)
    facing = impacts.Shooter("facing", [49, 50, 51], [(t, 0.0, 0.0, 0.0, 0.0) for t in (49, 50, 51)])
    away = impacts.Shooter("away", [50], [(50, 0.0, 5.0, 0.0, 90.0)])
    dead = impacts.Shooter("dead", [50], [(50, 0.0, 0.1, 0.0, 0.0)], dead_at=10)
    (who, conf), = impacts.attribute([mark], [facing, away, dead])
    assert who == "facing" and 0.3 < conf <= 1.0
    (who, conf), = impacts.attribute([mark], [away])
    assert who is None and math.isnan(conf)


def test_sites_table_entry_when_no_room_was_walked(monkeypatch):
    monkeypatch.setattr(sites, "table", lambda: {"1": {"sites": {"2F Gym, 2F Bedroom": {"x": 1, "y": 2, "z": 4.3,
                                                                                       "r": 6}}}})
    objs = sites.objectives("1", [], {})
    assert objs[0]["shape"] == "cylinder" and objs[0]["radius"] == 6 and objs[0]["rounds"] == []


def test_gadget_type_by_how_it_moved():
    from heat3d_ext_r6.output import gadget_type
    kit = {"gadget": "Impact Grenade", "ability": "Kiba Barrier"}
    flew = [(t, t * 0.5, 0.0, 1.0) for t in range(10)]
    stayed = [(t, 1.0, 1.0, 0.0) for t in range(10)]
    assert gadget_type(kit, flew) == ("Impact Grenade", 0.7)
    assert gadget_type(kit, stayed) == ("Kiba Barrier", 0.6)
    name, conf = gadget_type({"gadget": "Barbed Wire", "ability": "Armor Panel"}, stayed)
    assert name == "Barbed Wire / Armor Panel" and math.isnan(conf)


def test_reinforcements_from_the_team_count():
    from heat3d_ext_r6.round import _reinforcements

    def field(v):
        return b"\x23" + struct.pack("<I", 0xF016002E) + b"\x00" * 4 + b"\x67\xde\x20\xf8\x04" + struct.pack("<I", v)

    rec = _Rec(b"\x00" * 16, [(100, field(10)), (200, field(9)), (400, field(8))])
    still = Player("still", 1, objects={1: "operator"})
    walker = Player("walker", 1, objects={2: "operator"})
    tracks = {1: [(t, 3.0, 3.0, 0.0) for t in range(0, 600, 5)], 2: [(t, t * 0.1, 0.0, 0.0) for t in range(0, 600, 5)]}
    ev = _reinforcements(rec, [still, walker], tracks, {1: "defense"}, [])
    assert [(e.tick, e.player, e.text, e.confidence) for e in ev] == [(200, "still", "9", 1.0), (400, "still", "8", 1.0)]
