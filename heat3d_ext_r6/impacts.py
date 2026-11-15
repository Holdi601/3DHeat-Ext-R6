"""
Marks left on the level: bullet holes and the like, each where it was made.

One of the tick-indexed sections (found by its content: the most records of
the form below) holds, per tick, records

    surface:u64  kind:u64  1.0 1.0 1.0 1.0  x y z:f32  rotation:4 f32
    8 zero bytes  scale x y z:f32 (1, 1, 0.05 in every record seen)  ...

`surface` is the level object the mark sits on. Its ids are the map's own
(they start with the map's `worldid`, e.g. 4071936xxxxx on Clubhouse whose
world id is 407193663917), so one wall, floor or barricade keeps its id
across the rounds and matches of one version of a map. `kind` is the mark's
type (a few dozen values; most marks of a round are a handful of kinds, as
bullet holes in different materials are). The position is in the level's
metres, Z up. The rotation (a quaternion) is not the world's: nearly every
record holds a half turn about one axis ((0, 1, 0, 0), (-1, 0, 0, 0)), so
its thin axis points straight up or down whether the mark sits on a wall or
a floor. It is the mark's turn in its surface's own frame, whose placement
the file does not give here, so no direction is written for a mark.

What the file does not say here: who made a mark and with what. The marks
are the client's record of holes and impacts, written without the shot that
made them; the opening a hole makes in a soft wall is not given as an area.
`attribute` works the shooter out where it can: the player facing the mark
when it appeared (the body's heading within 2 degrees, or 0.4 m to the side
at the mark's distance), with a confidence; the weapon only where that
player's kill in the same moment names it. Checked on a pro match: 89% of
the marks have a player facing them as they appear; with the marks' times
moved by 7 s, 22% do. So about three attributions in four name the shooter,
and one in four a player who happened to face that way.

Worked out here from the files.
"""

from __future__ import annotations

import bisect
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


#: How far off the body's heading a mark may be and still be the player's: degrees, or metres to the side.
AIM_DEG = 2.0
AIM_SIDE = 0.4
#: A mark further than this is nobody's (metres).
MAX_RANGE = 80.0
#: Ticks between a mark and the body sample that says where the player stood and faced.
NEAR_TICKS = 3


@dataclass
class Shooter:
    name: str
    ticks: list[int]
    samples: list[tuple[int, float, float, float, float]]  # tick, x, y, z, heading (degrees from +X, ccw)
    dead_at: int | None = None


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def attribute(marks: list[Impact], shooters: list[Shooter]) -> list[tuple[str | None, float]]:
    """
    Per mark, (player, confidence 0-1) where one player alone faced it as it
    appeared, (None, nan) where nobody did. Two players both facing it halve
    the confidence and the nearer to their heading is named.
    """
    out: list[tuple[str | None, float]] = []
    for m in marks:
        cands = []
        for s in shooters:
            if s.dead_at is not None and m.tick > s.dead_at + 1:
                continue
            i = bisect.bisect_left(s.ticks, m.tick)
            best = None
            for j in (i - 1, i):
                if 0 <= j < len(s.ticks) and abs(s.ticks[j] - m.tick) <= NEAR_TICKS:
                    if best is None or abs(s.ticks[j] - m.tick) < abs(best[0] - m.tick):
                        best = s.samples[j]
            if best is None or not math.isfinite(best[4]):
                continue
            dx, dy = m.x - best[1], m.y - best[2]
            dist = math.hypot(dx, dy)
            if dist < 0.5 or dist > MAX_RANGE:
                continue
            err = abs(_wrap(math.degrees(math.atan2(dy, dx)) - best[4]))
            limit = max(AIM_DEG, math.degrees(math.atan2(AIM_SIDE, dist)))
            if err <= limit:
                cands.append((err / limit, s.name))
        if not cands:
            out.append((None, float("nan")))
            continue
        cands.sort()
        conf = 1.0 - cands[0][0]
        if len(cands) > 1:
            conf *= 0.5
        out.append((cands[0][1], round(max(0.05, conf), 3)))
    return out