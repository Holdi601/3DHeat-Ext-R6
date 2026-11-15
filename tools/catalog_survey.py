"""
Survey replays for the catalogue: per round and player the operator and the item ids carried (as the action
phase starts), and each kill's item id and headshot. No player names are written.

    python tools/catalog_survey.py out.jsonl rounds_per_bundle <bundle.zip | folder>...

Rounds are spread over each bundle's matches. Appends to `out.jsonl` and skips rounds already in it, so it can
be stopped and run again. Then `tools/catalog_build.py` names the ids.
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heat3d_ext_r6 import game, loadout, rec as R, round as RD  # noqa: E402


def one(path: Path, src: str) -> dict:
    r = R.read(path)
    players = RD._players(r)
    first: dict[int, tuple[float, int]] = {}
    for t, ph, left in RD._anchors(r):
        first.setdefault(ph, (left, t))
    action = max(first.values())[1] if first else None
    lo = loadout.read(r, action)
    idx = {p.name: i for i, p in enumerate(players)}
    b = r.body
    kills = []
    p = b.find(RD.KILL, r.snapshot_end)
    while p != -1:
        d = RD._fields(b, p, p + 600)
        victim = d.get(bytes.fromhex("ac190f70"))
        if victim:
            w = d.get(RD.WEAPON, b"")
            hs = d.get(bytes.fromhex("c35ba44e"), b"")
            kills.append({"k": idx.get(d.get(bytes.fromhex("d9133cba"), b"").decode("utf-8", "replace")),
                          "v": idx.get(victim.decode("utf-8", "replace")),
                          "w": int.from_bytes(w, "little") if len(w) == 8 else None,
                          "hs": hs[0] if len(hs) == 1 else None})
        p = b.find(RD.KILL, p + 5)
    out = []
    for pl in players:
        x = lo.get(pl.name)
        out.append({"op": game.operator_name(x.operator_id) if x and x.operator_id else pl.operator,
                    "team": pl.team, "items": [[i.id, i.weapon, i.skin] for i in x.items] if x else []})
    return {"src": src, "version": r.header.get("version"), "map": game.map_name(r.header.get("worldid")),
            "players": out, "kills": kills}


def main(argv: list[str]) -> None:
    out_path, per, sources = Path(argv[0]), int(argv[1]), argv[2:]
    done = set()
    if out_path.exists():
        done = {json.loads(line)["src"] for line in out_path.open(encoding="utf-8")}
    with out_path.open("a", encoding="utf-8") as out, tempfile.TemporaryDirectory() as tmp:
        tmp_rec = Path(tmp) / "round.rec"
        for s in sources:
            p = Path(s)
            if p.suffix.lower() == ".zip":
                with zipfile.ZipFile(p) as zf:
                    names = sorted(n for n in zf.namelist() if n.lower().endswith(".rec"))
                    for n in names[:: max(1, len(names) // per)][:per]:
                        src = f"{p.name}|{n}"
                        if src in done:
                            continue
                        tmp_rec.write_bytes(zf.read(n))
                        try:
                            out.write(json.dumps(one(tmp_rec, src)) + "\n")
                        except (R.RecError, ValueError, IndexError) as e:
                            print("skipped", src, e, file=sys.stderr)
            else:
                files = sorted(p.rglob("*.rec")) if p.is_dir() else [p]
                for f in files[:: max(1, len(files) // per)][:per]:
                    if str(f) not in done:
                        out.write(json.dumps(one(f, str(f))) + "\n")
            out.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
