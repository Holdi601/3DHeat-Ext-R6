"""Shots, reloads, ability and gadget uses on synthetic data (`items.py`), and which gadget object a use put out."""

from __future__ import annotations

import struct
from types import SimpleNamespace

from heat3d_ext_r6 import items, output
from heat3d_ext_r6.round import Player

REC, INV = 0xF0160001, 0xF0160002
WEAPON, W_HOLDER, W_ITEM, W_LINK, AMMO = 0xF0170001, 0xF0170002, 0xF0170003, 0xF0170004, 0xF0170005
GADGET, G_HOLDER, G_ITEM, CHARGE1, CHARGE2 = 0xF0170011, 0xF0170012, 0xF0170013, 0xF0170014, 0xF0170015
ABILITY, A_HOLDER, A_ITEM = 0xF0170021, 0xF0170022, 0xF0170023
RIFLE, GRENADE, CAMERA = 1001, 1002, 1003

H = bytes.fromhex


def o(x: int) -> bytes:
    return struct.pack("<Q", x)


def u32(v: int) -> bytes:
    return struct.pack("<I", v)


def link(parent: int, child: int, cls: str, field: str = "a57aaa29") -> bytes:
    return b"\x1b" + o(parent) + H(field) + o(child) + H(cls)


def child(field: str, obj: int, cls: str) -> bytes:
    return b"\x1a" + H(field) + o(obj) + H(cls)


def element(field: str, index: int, obj: int, cls: str) -> bytes:
    return b"\x1e" + H(field) + u32(index) + o(obj) + H(cls)


def put(obj: int, field: str, value: bytes, *more: tuple[str, bytes]) -> bytes:
    out = b"\x23" + o(obj) + H(field) + bytes([len(value)]) + value
    for f, v in more:
        out += b"\x22" + H(f) + bytes([len(v)]) + v
    return out


def slot(parent_field: str, slot_obj: int, cls: str, holder: int, item_obj: int, item_cls: str, item_id: int) -> bytes:
    return (link(INV, slot_obj, cls, parent_field) + put(slot_obj, "3bd73fc1", b"\x00")
            + child("d19c5716", holder, "7882de67") + link(holder, item_obj, item_cls)
            + put(item_obj, "0e9ebe88", o(item_id)))


class _Rec:
    """Just enough of a Rec: a snapshot, an event section of ticked blocks."""

    def __init__(self, snapshot: bytes, ticks: list[tuple[int, bytes]]):
        self.body = snapshot
        self.snapshot_end = len(snapshot)
        self._at: list[tuple[int, int, int]] = []
        for tick, data in ticks:
            self._at.append((len(self.body), len(self.body) + len(data), tick))
            self.body += data
        self.sections = [SimpleNamespace(index=3, start=self.snapshot_end, end=len(self.body))]

    def tick_at(self, off: int):
        for a, b, t in self._at:
            if a <= off < b:
                return t
        return None


def _round() -> _Rec:
    snap = (link(REC, INV, "579fb57b", "e8d1e539")
            # a rifle: 30 in the magazine, 150 in all
            + slot("9327a12b", WEAPON, "0eaa2be0", W_HOLDER, W_ITEM, "ec5ff8fa", RIFLE)
            + link(WEAPON, W_LINK, "5f85cc85") + child("1ed17fd6", AMMO, "af99e10b")
            + put(AMMO, "77ca96de", u32(30), ("400ac829", u32(150)), ("dd263e65", b"\x00"))
            # a grenade with two charges, each its own object
            + slot("d890b5f7", GADGET, "9f44690a", G_HOLDER, G_ITEM, "74264e2e", GRENADE)
            + put(GADGET, "b010fa49", b"\x01")
            + element("b010fa49", 0, CHARGE1, "2165e792") + element("b010fa49", 1, CHARGE2, "2165e792")
            + put(CHARGE1, "fffd5262", u32(0)) + put(CHARGE2, "fffd5262", u32(0))
            # an ability counted by its charges left (not written until they change)
            + slot("4cd6a0c7", ABILITY, "9f44690a", A_HOLDER, A_ITEM, "74264e2e", CAMERA))
    ticks = [
        (10, put(AMMO, "77ca96de", u32(27), ("400ac829", u32(147)))),  # three shots
        (12, put(AMMO, "77ca96de", u32(26), ("400ac829", u32(146)))),  # one more
        (20, put(AMMO, "dd263e65", b"\x01")),  # a reload: the total stays
        (21, put(AMMO, "77ca96de", u32(30), ("400ac829", u32(146)), ("dd263e65", b"\x00"))),
        (30, put(CHARGE1, "fffd5262", u32(1))),  # thrown and still out
        (40, put(CHARGE1, "fffd5262", u32(2))),  # set off
        (45, put(CHARGE2, "fffd5262", u32(2))),  # thrown and gone at once
        (50, put(ABILITY, "3bd73fc1", b"\x01")),  # the ability in hand
        (60, put(ABILITY, "3bd73fc1", b"\x00", ("14d1bd4f", u32(2)))),  # put away: one used
        (70, put(ABILITY, "14d1bd4f", u32(1))),  # another
    ]
    return _Rec(snap, ticks)


KINDS = {RIFLE: "primary", GRENADE: "gadget", CAMERA: "ability"}


def test_uses_from_the_item_tree():
    rec = _round()
    pl = Player("alpha", 0)
    pl.item_objects = [(W_ITEM, RIFLE), (G_ITEM, GRENADE), (A_ITEM, CAMERA)]
    uses = items.read(rec, 3, [pl], KINDS.get, {REC: "alpha"})
    got = [(u.kind, u.tick, u.item, u.count, u.left) for u in uses]
    assert got == [("shot", 10, RIFLE, 3, 147), ("shot", 12, RIFLE, 1, 146), ("reload", 20, RIFLE, 1, None),
                   ("gadget_deploy", 30, GRENADE, 1, None), ("gadget_destroyed", 40, GRENADE, 1, None),
                   ("gadget_deploy", 45, GRENADE, 1, None), ("ability_use", 60, CAMERA, 1, 2),
                   ("ability_use", 70, CAMERA, 1, 1)]
    assert all(u.player == "alpha" for u in uses)
    assert [u.charge for u in uses if u.item == GRENADE] == [CHARGE1, CHARGE1, CHARGE2]


def test_slots_found_through_the_players_record():
    """No item objects from the loadout: the inventory under the player's record still names the player."""
    rec = _round()
    uses = items.read(rec, 3, [Player("alpha", 0)], KINDS.get, {REC: "alpha"})
    assert sum(u.count for u in uses if u.kind == "shot") == 4
    assert items.read(rec, 3, [Player("alpha", 0)], KINDS.get, {}) == []


def test_a_use_names_the_gadget_object_it_put_out():
    track = [(t, 1.0 + 0.5 * min(t - 25, 10), 2.0, 0.0, 0.0, 0x80, 60) for t in range(25, 60)]
    far = [(t, 9.0, 9.0, 0.0, 0.0, 0x80, 60) for t in range(400, 420)]
    pl = Player("alpha", 0, objects={1: "operator", 2: "gadget", 3: "gadget"})
    deploy = items.Use("gadget_deploy", 30, "alpha", GRENADE, 1, None, CHARGE1, True)
    gone = items.Use("gadget_destroyed", 40, "alpha", GRENADE, 1, None, CHARGE1)
    shot = items.Use("shot", 31, "alpha", RIFLE, 1, 10)
    r = SimpleNamespace(uses=[deploy, gone, shot], players=[pl], tracks={2: track, 3: far, 1: []})
    used_by, use_track, uses = output.match_uses(r)
    assert used_by == {2: deploy}
    assert use_track[id(deploy)] == 2 and use_track[id(gone)] == 2 and id(shot) not in use_track
    assert [u.kind for u in uses] == ["gadget_deploy", "shot", "gadget_destroyed"]
