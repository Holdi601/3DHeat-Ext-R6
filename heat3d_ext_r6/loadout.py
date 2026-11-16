"""
Each player's operator and loadout as the round starts its action phase.

The snapshot region and the event section replicate objects in a tagged form:

    1b <object:u64> <hash:u32> ...        an object's record, its fields follow
    23 <object:u64> <field:u32> <len:u8> <value>   a field set on an object
    22 <field:u32> <len:u8> <value>       a further field of the same object

A player's record (`1b <player object> 27 c0 8d ca`, then the name under
`07 94 9b dc`) carries the operator under `a9 26 0b e4` (64-bit id). Each
item the player carries is an object of its own whose field `0e 9e be 88`
is the item's 64-bit id (the weapon, the gadget, the ability, an attacker's
drone) and `b2 97 ef 0c` its cosmetic (skin) id; the items stand just before
the record of the player they belong to.

In the preparation phase a player who picks another operator gets a new set
of items and an update of the record's operator field, in the event section,
in the same tick and in that order. So the loadout is followed tick by tick:
the operator and items last set before the action phase are the round's.

Item objects are of two kinds by the class their slot names: `ec 5f f8 fa`
a weapon (primary, then secondary), `74 26 4e 2e` a gadget, an ability or
the drone. The kill feed's weapon field (`f8 6c dd 65`) holds the same item
ids, so a kill names the weapon or gadget it was made with.

All of this was worked out here from the files.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from .rec import Rec

ITEM = b"\x0e\x9e\xbe\x88\x08"
SKIN = b"\x22\xb2\x97\xef\x0c\x08"
OPERATOR = b"\xa9\x26\x0b\xe4\x08"
NAME = b"\x22\x07\x94\x9b\xdc"
PLAYER_RECORD = b"\x27\xc0\x8d\xca"
LINK = b"\xa5\x7a\xaa\x29"
WEAPON_SLOT = b"\xec\x5f\xf8\xfa"
GADGET_SLOT = b"\x74\x26\x4e\x2e"


@dataclass
class Item:
    id: int
    skin: int | None
    weapon: bool | None  # by the slot's class; None where no slot was found
    obj: int | None = None  # the item object (`items.py` follows its slot)


@dataclass
class Loadout:
    name: str
    record: bytes  # the player record's object id, 8 bytes as in the file
    operator_id: int | None = None
    items: list[Item] = field(default_factory=list)
    changes: list[tuple[int | None, int]] = field(default_factory=list)  # (tick, operator id) as set
    held: list[Item] = field(default_factory=list)  # every item set held before the action phase, in order


def _item_at(b: bytes, p: int) -> tuple[bytes | None, Item]:
    """The item field at `p` (`0e 9e be 88 08`): its object and the item."""
    v = struct.unpack_from("<Q", b, p + 5)[0]
    skin = struct.unpack_from("<Q", b, p + 19)[0] if b[p + 13 : p + 19] == SKIN else None
    obj = b[p - 8 : p] if p >= 9 and b[p - 9] == 0x23 else None
    weapon = None
    if obj is not None:
        k = b.rfind(LINK + obj, max(0, p - 240), p)
        if k >= 0:
            cls = b[k + 12 : k + 16]
            weapon = True if cls == WEAPON_SLOT else False if cls == GADGET_SLOT else None
    return obj, Item(v, skin or None, weapon, struct.unpack("<Q", obj)[0] if obj is not None else None)


def _records(b: bytes, end: int) -> list[tuple[int, bytes, str]]:
    """(offset, record object, name) of each player record in the snapshot region."""
    out = []
    for m in re.finditer(re.escape(NAME), b[:end]):
        p = m.start()
        n = b[p + 5]
        name = b[p + 6 : p + 6 + n].decode("utf-8", "replace")
        k = b.rfind(PLAYER_RECORD, max(0, p - 120), p)
        if k >= 9 and b[k - 9] == 0x1B and name:
            out.append((p, b[k - 8 : k], name))
    return out


def read(rec: Rec, action_tick: int | None) -> dict[str, Loadout]:
    """Each player's loadout by name, as set before `action_tick` (the whole recording when None)."""
    b = rec.body
    end = rec.snapshot_end
    recs = _records(b, end)
    out: dict[str, Loadout] = {}
    by_record: dict[bytes, Loadout] = {}
    # The snapshot: items stand before the record they belong to.
    items = []
    p = b.find(ITEM, 0, end)
    while p != -1:
        items.append((p, *_item_at(b, p)))
        p = b.find(ITEM, p + 1, end)
    prev = 0
    for pos, obj, name in recs:
        if name in out:
            prev = pos
            continue
        lo = Loadout(name, obj)
        lo.items = [it for q, _o, it in items if prev < q < pos and it.id]
        lo.held = list(lo.items)
        k = b.find(OPERATOR, pos, pos + 400)
        if k >= 0:
            lo.operator_id = struct.unpack_from("<Q", b, k + 5)[0] or None
            lo.changes.append((None, lo.operator_id or 0))
        out[name] = lo
        by_record[obj] = lo
        prev = pos
    # The event section: an operator set on a record, the items set just before it in the same tick.
    for blk in rec.blocks:
        if blk.section != _event_section(rec) or (action_tick is not None and blk.tick >= action_tick):
            continue
        q = b.find(OPERATOR, blk.start, blk.end)
        if q == -1:
            continue
        found = []
        p = b.find(ITEM, blk.start, blk.end)
        while p != -1:
            found.append((p, _item_at(b, p)[1]))
            p = b.find(ITEM, p + 1, blk.end)
        last = blk.start
        while q != -1:
            owner = None
            for obj, lo in by_record.items():
                k = b.rfind(b"\x23" + obj, max(blk.start, q - 64), q)
                if k >= 0:
                    owner = lo
                    break
            if owner is not None:
                op = struct.unpack_from("<Q", b, q + 5)[0]
                mine = [it for p2, it in found if last < p2 < q and it.id]
                if op:
                    owner.operator_id = op
                    owner.changes.append((blk.tick, op))
                if mine:
                    owner.items = mine
                    owner.held += mine
                last = q
            q = b.find(OPERATOR, q + 5, blk.end)
    return out


def _event_section(rec: Rec) -> int:
    """The section holding the round clock and kill feed (the third after the object stream, by content)."""
    if getattr(rec, "_event_section", None) is None:
        best, n = 3, -1
        for s in rec.sections:
            c = rec.body.count(OPERATOR, s.start, s.end)
            if c > n:
                best, n = s.index, c
        rec._event_section = best  # type: ignore[attr-defined]
    return rec._event_section  # type: ignore[attr-defined]
