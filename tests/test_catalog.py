"""The loadout, the marks and the catalogue on synthetic bytes (no replay needed)."""

from __future__ import annotations

import struct
from pathlib import Path

from heat3d_ext_r6 import catalog, impacts, loadout, output
from heat3d_ext_r6.rec import Block, Rec, Section
from heat3d_ext_r6.round import Player

OBJ = lambda n: struct.pack("<II", 0xF0000000 | n, 0)  # noqa: E731
Q = lambda v: struct.pack("<Q", v)  # noqa: E731
DRONE = int(catalog.data()["drone"])
#: Ids the catalogue names for sure (looked up, so the test follows a rebuilt catalogue).
SURE = {v["name"]: int(k) for k, v in catalog.data()["items"].items() if v["sure"]}


def item(obj: int, value: int, weapon: bool) -> bytes:
    cls = loadout.WEAPON_SLOT if weapon else loadout.GADGET_SLOT
    return (b"\x1b" + OBJ(obj + 100) + loadout.LINK + OBJ(obj) + cls
            + b"\x23" + OBJ(obj) + loadout.ITEM + Q(value) + loadout.SKIN + Q(0))


def record(obj: int, name: str, op: int) -> bytes:
    n = name.encode()
    return (b"\x1b" + OBJ(obj) + loadout.PLAYER_RECORD + b"\x22\x01\x02\x03\x04\x01\x00"
            + loadout.NAME + bytes([len(n)]) + n + b"\x22" + loadout.OPERATOR + Q(op))


def test_loadout_follows_a_pick_in_preparation():
    ak, p9 = SURE["AK-12"], SURE["P9"]
    snap = item(1, DRONE, False) + item(2, SURE["MP7"], True) + record(50, "alpha", 92270642656)  # Ash at the start
    block = item(3, DRONE, False) + item(4, ak, True) + item(5, p9, True) + item(6, SURE["Claymore"], False) \
        + b"\x23" + OBJ(50) + b"\xf9\x39\x11\xf2\x08" + Q(1) + b"\x22" + loadout.OPERATOR + Q(104189664390)  # Ace
    body = snap + bytes(16) + block
    start = len(snap) + 16
    rec = Rec(Path("x.rec"), {}, [], [], body, True, 1)
    rec.snapshot_end = len(snap)
    rec.sections = [Section(0, "00", 0, 0, len(snap), len(snap) + 16, 1, 1, 1),
                    Section(1, "01", 0, 0, start, len(body), 1, 10, 10)]
    rec.blocks = [Block(1, 10, start, len(body))]
    rec._starts = [b.start for b in rec.blocks]
    lo = loadout.read(rec, action_tick=100)["alpha"]
    assert lo.operator_id == 104189664390
    assert [c[1] for c in lo.changes] == [92270642656, 104189664390]
    assert [i.id for i in lo.items] == [DRONE, ak, p9, SURE["Claymore"]]
    assert [i.weapon for i in lo.items] == [False, True, True, False]
    # Before the pick (the action phase starting earlier), the snapshot's loadout stands.
    assert loadout.read(rec, action_tick=5)["alpha"].operator_id == 92270642656


def test_gear_names_slots_classes_and_roles():
    p = Player("alpha", 0, operator="Ace")
    p.items = [loadout.Item(DRONE, None, False), loadout.Item(SURE["AK-12"], None, True),
               loadout.Item(SURE["P9"], None, True), loadout.Item(SURE["Claymore"], None, False)]
    g = output.gear(p)
    assert (g["primary"], g["primaryClass"]) == ("AK-12", "assault rifle")
    assert (g["secondary"], g["secondaryClass"]) == ("P9", "handgun")
    assert (g["gadget"], g["gadgetRole"]) == ("Claymore", "trap")
    assert g["operatorRole"] == "hard breacher"
    assert g["loadout"] == "AK-12|P9|Claymore"
    assert output.label(1234)[0] == "item 1234"


def test_catalogue_facts():
    assert catalog.role_of("Capitao") == catalog.role_of("Capitão") == "flex"
    assert catalog.describe("Barbed Wire", "gadget") == {"role": "denial", "side": "defense"}
    assert catalog.describe("Le Roc Shield", "primary") == {"class": "shield"}
    assert catalog.item(DRONE)["kind"] == "drone"


def test_marks_with_surface_and_normal():
    # A mark facing +Y (rotation of -90 degrees about X): normal (0, 1, 0).
    s = 2 ** -0.5
    rec_bytes = (Q(407193681622) + Q(9890127690) + impacts.ONES + struct.pack("<3f", 1.0, 2.0, 3.0)
                 + struct.pack("<4f", -s, 0.0, 0.0, s) + bytes(12) + struct.pack("<3f", 1.0, 1.0, 0.05) + b"\x00\x01")
    body = bytes(8) + rec_bytes + bytes(8)
    rec = Rec(Path("x.rec"), {}, [], [], body, True, 1)
    rec.sections = [Section(0, "00", 0, 0, 0, 0, 0, None, None), Section(1, "06", 0, 0, 0, len(body), 1, 7, 7)]
    rec.blocks = [Block(1, 7, 0, len(body))]
    rec._starts = [0]
    (m,) = impacts.read(rec)
    assert (m.tick, m.surface, m.kind) == (7, 407193681622, 9890127690)
    assert (m.x, m.y, m.z) == (1.0, 2.0, 3.0)
    assert abs(m.nx) < 1e-6 and abs(m.ny - 1) < 1e-6 and abs(m.nz) < 1e-6
