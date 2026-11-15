"""
Marks left on the level: bullet holes and the like, each where it was made.

One of the tick-indexed sections (found by its content: the most records of
the form below) holds, per tick, records

    surface:u64  kind:u64  1.0 1.0 1.0 1.0  x y z:f32  rotation:4 f32
    12 bytes  scale x y z:f32 (1, 1, 0.05 in every record seen)  2 flag bytes

`surface` is the level object the mark sits on. Its ids are the map's own
(they start with the map's `worldid`, e.g. 4071936xxxxx on Clubhouse whose
world id is 407193663917), so one wall, floor or barricade keeps its id
across the rounds and matches of one version of a map. `kind` is the mark's
type (a few dozen values; most marks of a round are a handful of kinds, as
bullet holes in different materials are). The position is in the level's
metres, Z up; the rotation (a quaternion) turns the mark's face onto the
surface, so its third axis is the surface's normal.

What the file does not say here: who made a mark and with what. The marks
are the client's record of holes and impacts, written without the shot that
made them; the opening a hole makes in a soft wall is not given as an area.

Worked out here from the files.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from .rec import Rec

ONES = b"\x00\x00\x80\x3f" * 4


@dataclass
class Impact:
    tick: int
    surface: int
    kind: int
    x: float
    y: float
    z: float
    nx: float
    ny: float
    nz: float
    scale: float


def _section(rec: Rec) -> int | None:
    best, n = None, 0
    for s in rec.sections[1:]:
        c = rec.body.count(ONES, s.start, s.end)
        if c > n:
            best, n = s.index, c
    return best if n >= 1 else None


def read(rec: Rec) -> list[Impact]:
    sec = _section(rec)
    if sec is None:
        return []
    s = rec.sections[sec]
    b = rec.body
    unpack = struct.unpack_from
    out: list[Impact] = []
    p = b.find(ONES, s.start, s.end)
    while p != -1:
        if p - 16 >= s.start and p + 72 <= s.end:
            surface, kind = unpack("<QQ", b, p - 16)
            x, y, z = unpack("<3f", b, p + 16)
            qx, qy, qz, qw = unpack("<4f", b, p + 28)
            sx = unpack("<f", b, p + 56)[0]
            tick = rec.tick_at(p)
            if tick is not None and 0 < surface < 1 << 40 and 0 < kind < 1 << 40 and all(math.isfinite(v) and abs(v) < 5000 for v in (x, y, z)) \
                    and abs(qx * qx + qy * qy + qz * qz + qw * qw - 1) < 0.05:
                # The quaternion's third axis: the surface normal.
                nx = 2 * (qx * qz + qw * qy)
                ny = 2 * (qy * qz - qw * qx)
                nz = 1 - 2 * (qx * qx + qy * qy)
                out.append(Impact(tick, surface, kind, x, y, z, nx, ny, nz, sx if math.isfinite(sx) else float("nan")))
        p = b.find(ONES, p + 16, s.end)
    return out
