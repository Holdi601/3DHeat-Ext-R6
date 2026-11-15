"""
heat3d-r6-replay: Rainbow Six Siege Match Replays into 3DHeat matches.

    heat3d-r6-replay <file.rec | match folder | folder of matches | bundle.zip>... -o <out> [--loose]
    heat3d-r6-replay info <file.rec>

A match is the folder of its rounds (`Match-<date>-<id>/...-R01.rec`); each
becomes one `<match>.3dheat`. Zip bundles (the esports downloads) are read in
place, without unpacking them to disk.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from . import __version__, container, output
from .rec import RecError, read
from .round import read_round


def _matches(paths: list[str]) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for a in paths:
        p = Path(a)
        files = [p] if p.is_file() and p.suffix.lower() == ".rec" else sorted(p.rglob("*.rec")) if p.is_dir() else []
        for f in files:
            out.setdefault(str(f.parent), []).append(f)
    return out


def convert(files: list[Path], out: Path, loose: bool = False) -> Path | None:
    rounds = []
    for f in sorted(files):
        try:
            rounds.append(read_round(read(f)))
        except (RecError, OSError, ValueError, IndexError) as e:
            print(f"  skipped {f.name}: {e}", file=sys.stderr)
    if not rounds:
        return None
    data = output.write(rounds, out)
    if loose:
        return data
    first = rounds[0]
    return container.pack(data, {
        "game": "r6siege", "source": "match replay", "converter": {"name": "heat3d-r6-replay", "version": __version__},
        "match": output.match_name(rounds), "map": first.map, "mode": first.mode,
        "started": first.rec.header.get("datetime"),
    })


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["info"]:
        for a in argv[1:]:
            r = read_round(read(a))
            print(json.dumps({"header": r.rec.header, "map": r.map, "site": r.site, "roles": r.roles,
                              "winner": r.winner, "condition": r.win_condition,
                              "players": [(p.name, p.team, p.operator, sorted(p.objects.values())) for p in r.players],
                              "events": [(e.kind, e.tick, e.clock, e.player, e.other) for e in r.events]},
                             indent=1, ensure_ascii=False))
        return 0
    ap = argparse.ArgumentParser(prog="heat3d-r6-replay", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--loose", action="store_true", help="keep the separate files instead of a .3dheat")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)
    out = Path(args.out)
    plain = [p for p in args.paths if not p.lower().endswith(".zip")]
    groups = _matches(plain)
    done = 0
    for z in (p for p in args.paths if p.lower().endswith(".zip")):
        with zipfile.ZipFile(z) as zf, tempfile.TemporaryDirectory() as tmp:
            names = [n for n in zf.namelist() if n.lower().endswith(".rec")]
            by: dict[str, list[str]] = {}
            for n in names:
                by.setdefault(n.rsplit("/", 1)[0], []).append(n)
            for folder, members in by.items():
                files = []
                for n in members:
                    target = Path(tmp) / Path(n).name
                    target.write_bytes(zf.read(n))
                    files.append(target)
                res = convert(files, out, args.loose)
                for f in files:
                    f.unlink()
                if res:
                    done += 1
                    print(res)
    for folder, files in groups.items():
        res = convert(files, out, args.loose)
        if res:
            done += 1
            print(res)
    print(f"{done} match(es) written to {out}", file=sys.stderr)
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
