"""
What each player did with what they carry: shots fired and reloads, every
use of the ability, every gadget thrown, placed, picked up or destroyed.

The snapshot region and the event section replicate a tree of objects in
the tagged form (`loadout.py`):

    1a <field:u32> <object:u64> <class:u32>           a child object under a field
                                                       of the object last named
    1b <object:u64> <field:u32> <child:u64> <class:u32>  a child linked to an object
    1e <field:u32> <index:u32> <object:u64> <class:u32>  an element of an array field
    23 <object:u64> <field:u32> <len:u8> <value>      a field set (`22 ...` more of them)

Each carried item is a small subtree, one per slot:

    slot object (class 0eaa2be0 for a weapon, 9f44690a for a gadget or ability)
      d19c5716 -> holder -> a57aaa29 -> item object (`0e 9e be 88`: the 64-bit item id)
      14d1bd4f    charges left (an ability's or gadget's count)
      3bd73fc1    in hand (1) or put away (0)
      1ed17fd6 -> ammunition object (class af99e10b):
                    77ca96de  rounds in the magazine
                    400ac829  rounds in all (magazine and reserve)
                    6d5b6d3e  reserve
                    dd263e65  reloading (1 while it lasts)
      b010fa49 -> [one object per charge of a deployable] (class 2165e792):
                    fffd5262  0 carried, 1 out (placed, thrown, deployed),
                              2 gone (used up, destroyed, detonated)

The item object stands in the player's record (`loadout.py`), so a slot
belongs to the player whose loadout holds its item object. A drop of the
rounds in all is that many shots fired; a drop of the charges is a use; a
charge going out is a gadget deployed, coming back a pick-up, and gone after
being out a gadget destroyed or set off.

Worked out here from the files.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from .rec import Rec

_OBJ = rb"(...\xf0\x00\x00\x00\x00)"
_CHILD = rb"(...\xf0\x00\x00\x00\x00|\x00{8})"
#: The records that name an object: a field set (`23`), a link (`1b`), a child (`1a`), an array element (`1e`).
#: Each is followed by further fields of the object last named (`22 <field> <len> <value>`, `26 <field>
#: <index:u32> <len> <value>` for an array's element).
TOKEN = re.compile(rb"\x23" + _OBJ + rb"(.{4})(.)"
                   rb"|\x1b" + _OBJ + rb".{4}" + _CHILD + rb"(.{4})"
                   rb"|\x1a.{4}" + _CHILD + rb"(.{4})"
                   rb"|\x1e.{8}" + _CHILD + rb"(.{4})", re.S)

ITEM_FIELD = bytes.fromhex("0e9ebe88")
CHARGES = bytes.fromhex("14d1bd4f")
IN_HAND = bytes.fromhex("3bd73fc1")
AMMO_TOTAL = bytes.fromhex("400ac829")
MAGAZINE = bytes.fromhex("77ca96de")
RELOADING = bytes.fromhex("dd263e65")
STATE = bytes.fromhex("fffd5262")
AMMO_CLASS = bytes.fromhex("af99e10b")
CHARGE_CLASS = bytes.fromhex("2165e792")
CHARGE_FIELD = bytes.fromhex("b010fa49")


@dataclass
class Use:
    kind: str  # shot, reload, ability_use, gadget_deploy, gadget_pickup, gadget_destroyed
    tick: int
    player: str
    item: int  # the item id (catalogue)
    count: int = 1  # shots or charges used at this tick
    left: int | None = None  # rounds in all or charges left after it
    charge: int | None = None  # the charge object (a gadget's deploy, pick-up, destruction)
    placed: bool = False  # something went out (thrown or placed): its object may be in the stream


@dataclass
class Tree:
    parent: dict[int, int]
    cls: dict[int, bytes]
    fields: dict[int, dict[bytes, list[tuple[int | None, int]]]]  # object -> field -> [(tick, value)]


def _u(b: bytes) -> int:
    return struct.unpack("<Q", b)[0]


def tree(rec: Rec, event_section: int) -> Tree:
    """The object tree and the field values set on it, snapshot (tick None) then the event section."""
    b = rec.body
    parent: dict[int, int] = {}
    cls: dict[int, bytes] = {}
    fields: dict[int, dict[bytes, list]] = {}
    regions = [(0, rec.snapshot_end, False)]
    regions += [(s.start, s.end, True) for s in rec.sections if s.index == event_section]
    for start, end, ticked in regions:
        cur = None
        pos = start
        while True:
            m = TOKEN.search(b, pos, end)
            if m is None:
                break
            g = m.groups()
            tick = rec.tick_at(m.start()) if ticked else None
            p = m.end()
            pending = None
            if g[0] is not None:  # a field set: the first field's value follows
                cur = _u(g[0])
                pending = (g[1], g[2][0])
            elif g[3] is not None:
                cur = _u(g[3])
                c = _u(g[4])
                if c:
                    parent[c], cls[c] = cur, g[5]
            else:
                c = _u(g[6] if g[6] is not None else g[8])
                if c and cur is not None:
                    parent[c], cls[c] = cur, g[7] if g[6] is not None else g[9]
            # The value and the further fields of the object last named, while they continue.
            while True:
                if pending is not None:
                    f, n = pending
                    if p + n > end:
                        break
                    if cur is not None and n in (1, 4, 8):
                        fields.setdefault(cur, {}).setdefault(f, []).append(
                            (tick, int.from_bytes(b[p:p + n], "little")))
                    p += n
                    pending = None
                if p + 6 <= end and b[p] == 0x22:
                    pending = (b[p + 1:p + 5], b[p + 5])
                    p += 6
                elif p + 10 <= end and b[p] == 0x26:  # an array's element: skipped
                    p += 10 + b[p + 9]
                else:
                    break
            pos = max(p, m.start() + 1)
    return Tree(parent, cls, fields)


def _steps(values: list[tuple[int | None, int]]) -> list[tuple[int | None, int]]:
    """The values as they changed (repeats dropped)."""
    out: list[tuple[int | None, int]] = []
    for t, v in values:
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out


def read(rec: Rec, event_section: int, players, kind_of, records: dict[int, str] | None = None) -> list[Use]:
    """
    Every use, by player. `players`: objects with `name` and `item_objects`
    ((item object, item id) of every item they held in the round);
    `kind_of(item id)`: the catalogue's kind (primary, secondary, gadget,
    ability, drone) or None; `records`: each player record's object and
    the player's name (`loadout._records`).
    """
    t = tree(rec, event_section)
    records = records or {}

    def slot_above(obj: int) -> int | None:
        holder = t.parent.get(obj)
        return t.parent.get(holder) if holder is not None else None

    # The slots of the items the loadout gives each player; their parent is the player's inventory, which
    # then names the player of every other slot in it (items given out later in the round, or missed there).
    votes: dict[int, dict[str, int]] = {}
    for pl in players:
        for obj, item_id in pl.item_objects:
            slot = slot_above(obj)
            inv = t.parent.get(slot) if slot is not None else None
            if inv is not None:
                v = votes.setdefault(inv, {})
                v[pl.name] = v.get(pl.name, 0) + 1
    inv_of = {}
    for inv, v in votes.items():  # the player most of its items are given to (a tie: nobody's)
        ranked = sorted(v.values(), reverse=True)
        if len(ranked) == 1 or ranked[0] > ranked[1]:
            inv_of[inv] = max(v, key=v.get)
    # Better: an inventory hangs under its player's record (`loadout.py`), where the tree says so.
    for inv in {t.parent.get(s) for s in map(slot_above, (o for o, f in t.fields.items() if ITEM_FIELD in f))}:
        owner = records.get(t.parent.get(inv)) if inv is not None else None
        if owner is not None:
            inv_of[inv] = owner
    slot_of: dict[int, tuple[str, int]] = {}  # slot object -> (player, item id)
    for obj, f in t.fields.items():
        ids = [v for _t, v in f.get(ITEM_FIELD, []) if v]
        slot = slot_above(obj) if ids else None
        if slot is not None and t.parent.get(slot) in inv_of:
            slot_of[slot] = (inv_of[t.parent[slot]], ids[-1])
    ammo: dict[int, list[int]] = {}
    charges: dict[int, list[int]] = {}
    for o, p in t.parent.items():
        if p in slot_of:
            if t.cls.get(o) == AMMO_CLASS:
                ammo.setdefault(p, []).append(o)
            elif t.cls.get(o) == CHARGE_CLASS:
                charges.setdefault(p, []).append(o)
    out: list[Use] = []
    for slot, (name, item_id) in slot_of.items():
        kind = kind_of(item_id)
        if kind == "drone":  # drones: their own objects in the stream say when each went out (`output.py`)
            continue
        ability = kind == "ability"
        counted = False
        for a in ammo.get(slot, []):
            f = t.fields.get(a, {})
            total = _steps(f.get(AMMO_TOTAL, []))
            for (t0, v0), (t1, v1) in zip(total, total[1:]):
                if t1 is not None and v1 < v0:
                    out.append(Use("ability_use" if ability else "shot", t1, name, item_id, v0 - v1, v1))
            counted = counted or bool(total)
            for t1, v in _steps(f.get(RELOADING, []))[1:]:
                if v == 1 and t1 is not None:
                    out.append(Use("reload", t1, name, item_id, 1, None))
        if counted:
            continue
        # A deployable's charges, each its own object: out, back, gone.
        mine = charges.get(slot, [])
        for c in mine:
            st = _steps(t.fields.get(c, {}).get(STATE, []))
            for (t0, v0), (t1, v1) in zip(st, st[1:]):
                if t1 is None:
                    continue
                if v0 == 0 and v1 in (1, 2):
                    out.append(Use("ability_use" if ability else "gadget_deploy", t1, name, item_id, 1, None, c, True))
                elif v0 == 1 and v1 == 0:
                    out.append(Use("gadget_pickup", t1, name, item_id, 1, None, c))
                elif v0 == 1 and v1 == 2:
                    out.append(Use("gadget_destroyed", t1, name, item_id, 1, None, c))
        if mine:
            continue
        # Otherwise the slot's count of charges left. It is written only once it changes, so the first value
        # written is a use when the item was in hand just before (put away after using it).
        left = _steps(t.fields.get(slot, {}).get(CHARGES, []))
        hand = [tk for tk, v in t.fields.get(slot, {}).get(IN_HAND, []) if v == 1 and tk is not None]
        prev = None
        for tk, v in left:
            if tk is None:
                prev = v
                continue
            used = prev - v if prev is not None else (1 if any(h <= tk for h in hand) else 0)
            if used > 0:  # (a rise is a refill, a regained or a picked-up charge: not told apart, not written)
                out.append(Use("ability_use" if ability else "gadget_deploy", tk, name, item_id, used, v, None, True))
            prev = v
    out.sort(key=lambda u: (u.tick, u.player, u.kind))
    return out
