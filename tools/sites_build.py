"""
The bomb-site table (`heat3d_ext_r6/sites.json`) from converted matches.

    python tools/sites_build.py survey <folder of .3dheat> <survey.jsonl>   # per round: site, plants, defenders
    python tools/sites_build.py build <survey.jsonl> [heat3d_ext_r6/sites.json]

Per map version (`worldid`) and site: the middle of the plants made there
(the median, so a plant from the doorway does not move it), the floor height
and the spread; where no plant was seen, the middle of the defenders' places
late in the preparation phase (they hold the site). Derived coordinates
only: no game asset, no player name. The survey reads only the columns it
needs from each container's table.
"""

from __future__ import annotations

import io
import json
import math
import re
import statistics
import struct
import sys
import zipfile
from pathlib import Path

#: Points a site needs to be listed.
MIN_POINTS = 3
#: A site name seen in fewer rounds than this share of the map's most played site is left out: the same site in
#: a misread.
MIN_SHARE = 0.01
#: The English callouts start with their floor: the table keeps those (a localised recording names sites its own way).
ENGLISH = re.compile(r"^(B|[1-9]F|EXT|RF) ")


class _Part(io.RawIOBase):
    """A stored ZIP member as a file of its own (Parquet reads its footer and columns in place)."""

    def __init__(self, path: Path, start: int, size: int):
        self.f = open(path, "rb")
        self.start, self.size, self.pos = start, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        n = max(0, min(len(b), self.size - self.pos))
        self.f.seek(self.start + self.pos)
        data = self.f.read(n)
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)

    def close(self):
        self.f.close()
        super().close()


def survey(root: Path, out: Path) -> None:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    done = {json.loads(line)["file"] for line in out.open(encoding="utf-8")} if out.exists() else set()
    with out.open("a", encoding="utf-8") as w:
        for p in sorted(root.rglob("*.3dheat")):
            if str(p) in done:
                continue
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
                doc = json.loads(z.read(next(n for n in names if n.endswith(".match.json"))))
                info = z.getinfo(next(n for n in names if n.endswith(".parquet") and ".entities." not in n))
            with open(p, "rb") as f:
                f.seek(info.header_offset)
                n, m = struct.unpack_from("<HH", f.read(30), 26)
            part = _Part(p, info.header_offset + 30 + n + m, info.compress_size)
            tb = pq.ParquetFile(part).read(columns=["time", "player", "side", "phase", "event", "x", "y", "z",
                                                   "round", "site"])
            part.close()
            ev = pc.cast(tb["event"], "string")
            keep = pc.or_(pc.is_in(ev, value_set=pa.array(["plant", "plant_start"])),
                          pc.and_(pc.equal(ev, "position"),
                                  pc.and_(pc.equal(pc.cast(tb["phase"], "string"), "prep"),
                                          pc.equal(pc.cast(tb["side"], "string"), "defense"))))
            t = tb.filter(keep).to_pydict()
            rounds: dict = {}
            for i in range(len(t["time"])):
                d = rounds.setdefault(t["round"][i], {"site": t["site"][i], "plants": [], "prep": {}})
                if t["event"][i] in ("plant", "plant_start"):
                    d["plants"].append((round(t["x"][i], 2), round(t["y"][i], 2), round(t["z"][i], 2), t["event"][i]))
                else:
                    d["prep"].setdefault(t["player"][i], []).append((t["time"][i], t["x"][i], t["y"][i], t["z"][i]))
            for r, d in rounds.items():
                defs = []
                for s in d["prep"].values():
                    s.sort()
                    tail = [q for q in s if q[0] >= s[-1][0] - 10]
                    defs.append([round(statistics.median(q[k] for q in tail), 2) for k in (1, 2, 3)])
                w.write(json.dumps({"file": str(p), "world": doc.get("world_id"), "map": doc.get("map"),
                                    "version": doc.get("game_version"), "round": r, "site": d["site"],
                                    "plants": d["plants"], "defenders": defs}) + "\n")


def _middle(pts: list, q: float = 0.8) -> dict:
    x = statistics.median(p[0] for p in pts)
    y = statistics.median(p[1] for p in pts)
    z = statistics.median(p[2] for p in pts)
    far = sorted(math.hypot(p[0] - x, p[1] - y) for p in pts)
    r = far[int(q * (len(far) - 1))]
    return {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "r": round(min(8.0, max(3.0, r)), 2)}


def build(src: Path, out: Path) -> dict:
    by: dict = {}
    for line in src.open(encoding="utf-8"):
        d = json.loads(line)
        if not d.get("site") or not d.get("world"):
            continue
        m = by.setdefault(d["world"], {"map": d.get("map"), "versions": set(), "sites": {}})
        m["versions"].add(d.get("version") or "")
        s = m["sites"].setdefault(d["site"], {"rounds": 0, "plants": [], "starts": [], "defenders": []})
        s["rounds"] += 1
        for p in d["plants"]:
            (s["plants"] if p[3] == "plant" else s["starts"]).append(p)
        s["defenders"].extend(d["defenders"])
    maps = {}
    for world, m in sorted(by.items()):
        sites = {}
        most = max(s["rounds"] for s in m["sites"].values())
        for name, s in sorted(m["sites"].items()):
            if not all(ENGLISH.match(r.strip()) for r in name.split(",")) or s["rounds"] < MIN_SHARE * most:
                continue
            pts, how = (s["plants"], "plants") if len(s["plants"]) >= MIN_POINTS else \
                (s["starts"], "plant attempts") if len(s["starts"]) >= MIN_POINTS else (s["defenders"], "defenders")
            if len(pts) < MIN_POINTS:
                continue
            sites[name] = {**_middle(pts, 0.5 if how == "defenders" else 0.8), "from": how, "points": len(pts), "rounds": s["rounds"]}
        if sites:
            maps[world] = {"map": m["map"], "versions": sorted(v for v in m["versions"] if v), "sites": sites}
    doc = {"format": "heat3d-r6-sites", "version": 1,
           "about": "Bomb sites per map version (worldid), derived from converted esports matches: the median of "
                    "the plants made on each site (else of the defenders late in the preparation phase), floor "
                    "height z and spread r in metres, Z up. Derived coordinates only; no game asset.",
           "maps": maps}
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["survey"]:
        survey(Path(a[1]), Path(a[2]))
    elif a[:1] == ["build"]:
        here = Path(__file__).resolve().parent.parent / "heat3d_ext_r6" / "sites.json"
        d = build(Path(a[1]), Path(a[2]) if len(a) > 2 else here)
        print(len(d["maps"]), "map versions,", sum(len(m["sites"]) for m in d["maps"].values()), "sites")
    else:
        print(__doc__)
