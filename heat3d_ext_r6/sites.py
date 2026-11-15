"""
The bomb sites as the match's objectives (the viewer's `objectives`, as War
Thunder's capture zones are written).

A site is two rooms ("B Church, B Arsenal Room"), each a callout
(`callouts.py`). A room's floor plan is where the players stood while their
callout said that room: the outline of those positions (the outermost few
dropped), on the room's floor. Every room the players walk through in the
match gets its outline that way, so each site of the match is drawn from the
match itself.

The replay names only the site of its own round. The map's other sites come
from `sites.json`, a table derived from the converted esports matches: per
map version (`worldid`) each site seen, with the middle of its plants (or,
where no plant was seen, of the defenders late in the preparation phase), its
floor height and spread. It holds derived coordinates only, no game asset. A
site of the table whose rooms no player walked in the match is drawn as a
circle of that spread.

Each site lists the rounds it was played in and when (`active`, the table's
seconds), so the viewer can light the site of the round shown.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from .callouts import rooms

_HERE = Path(__file__).resolve().parent
#: Positions a room needs for an outline.
MIN_SAMPLES = 25
#: Samples kept a room (every n-th when there are more).
MAX_SAMPLES = 4000


@lru_cache(maxsize=1)
def table() -> dict:
    p = _HERE / "sites.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("maps", {})


def _hull(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _q(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(q * (len(s) - 1))))]


def room_shape(samples: list[tuple[float, float, float]]) -> dict | None:
    """A room's outline from where players stood in it: the hull of all but the outermost 3%, on its floor."""
    if len(samples) < MIN_SAMPLES:
        return None
    xs = [s[0] for s in samples]
    ys = [s[1] for s in samples]
    mx, my = _q(xs, 0.5), _q(ys, 0.5)
    far = sorted(math.hypot(s[0] - mx, s[1] - my) for s in samples)
    cut = far[int(0.97 * (len(far) - 1))]
    kept = [s for s in samples if math.hypot(s[0] - mx, s[1] - my) <= cut]
    hull = _hull([(round(s[0], 2), round(s[1], 2)) for s in kept])
    if len(hull) < 3:
        return None
    z = round(_q([s[2] for s in kept], 0.2), 2)
    cx = sum(p[0] for p in hull) / len(hull)
    cy = sum(p[1] for p in hull) / len(hull)
    r = max(math.hypot(p[0] - cx, p[1] - cy) for p in hull)
    return {"points": [[p[0], p[1], z] for p in hull], "position": [round(cx, 2), round(cy, 2), z],
            "radius": round(r, 2)}


def objectives(world_id: str | None, played: list[tuple[str, int, float, float]],
               room_samples: dict[str, list[tuple[float, float, float]]]) -> list[dict]:
    """
    The bomb sites: `played` is (site, round, from, to) per round (the
    table's seconds), `room_samples` the positions per callout. The match's
    sites first, then the rest of the map's from the table.
    """
    known = table().get(str(world_id or ""), {}).get("sites", {})
    order: list[str] = []
    for site, *_ in played:
        if site and site not in order:
            order.append(site)
    for site in sorted(known):
        if site not in order:
            order.append(site)
    out: list[dict] = []
    for site in order:
        rounds = [r for s, r, *_ in played if s == site]
        active = [[round(a, 3), round(b, 3)] for s, _r, a, b in played if s == site]
        base = {"type": "bomb_site", "site": site, "team": None, "letter": "", "rounds": rounds, "active": active,
                "height": 2.5}
        drawn = False
        for room in rooms(site):
            shape = room_shape(room_samples.get(room, []))
            if shape is None:
                continue
            out.append({**base, "name": room, "shape": "outline", **shape, "from": "callouts"})
            drawn = True
        if not drawn and site in known:
            k = known[site]
            out.append({**base, "name": site, "shape": "cylinder", "position": [k["x"], k["y"], k["z"]],
                        "radius": k["r"], "points": [], "from": "table"})
    return out


def thin(samples: list, limit: int = MAX_SAMPLES) -> list:
    if len(samples) <= limit:
        return samples
    step = len(samples) / limit
    return [samples[int(i * step)] for i in range(limit)]
