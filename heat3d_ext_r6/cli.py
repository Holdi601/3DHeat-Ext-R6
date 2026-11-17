"""
heat3d-r6-replay: Rainbow Six Siege Match Replays into 3DHeat matches.

    heat3d-r6-replay <file.rec | match folder | folder of matches | bundle.zip>... -o <out> [--loose]
    heat3d-r6-replay --game <your game folder> -o <out>
    heat3d-r6-replay info <file.rec>

With `--game` (or `HEAT3D_R6_GAME`), the `MatchReplay` folder inside the game
folder you name is read: the game keeps your last matches there.

A match is the folder of its rounds (`Match-<date>-<id>/...-R01.rec`); each
becomes one `<match>.3dheat`. Zip bundles (the esports downloads) are read in
place, without unpacking them to disk.

The maps as 3D levels come from the separate tool heat3d-r6-maps
(github.com/Holdi601/3DHeat-Ext-R6-Maps).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from . import __version__, container, output
from .rec import read
from .round import read_round


def _matches(paths: list[str]) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for a in paths:
        p = Path(a)
        files = [p] if p.is_file() and p.suffix.lower() == ".rec" else sorted(p.rglob("*.rec")) if p.is_dir() else []
        for f in files:
            out.setdefault(str(f.parent), []).append(f)
    return out


def _zip_matches(zf: zipfile.ZipFile, out: Path, loose: bool, depth: int = 0):
    """Each match (folder of rounds) in a zip, read in place; zips inside it too (some bundles hold one)."""
    names = zf.namelist()
    by: dict[str, list[str]] = {}
    for n in names:
        if n.lower().endswith(".rec"):
            by.setdefault(n.rsplit("/", 1)[0] if "/" in n else "", []).append(n)
    with tempfile.TemporaryDirectory() as tmp:
        for members in by.values():
            files = []
            for n in members:
                target = Path(tmp) / Path(n).name
                target.write_bytes(zf.read(n))
                files.append(target)
            res = convert(files, out, loose)
            for f in files:
                f.unlink()
            if res:
                yield res
        for n in names:
            if n.lower().endswith(".zip") and depth < 3:
                inner = Path(tmp) / f"inner{depth}.zip"
                with zf.open(n) as src, open(inner, "wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)
                try:
                    with zipfile.ZipFile(inner) as z2:
                        yield from _zip_matches(z2, out, loose, depth + 1)
                except zipfile.BadZipFile as e:
                    print(f"  skipped {n}: {e}", file=sys.stderr)
                inner.unlink()


def convert(files: list[Path], out: Path, loose: bool = False) -> Path | None:
    rounds = []
    for f in sorted(files):
        try:
            rounds.append(read_round(read(f)))
        except Exception as e:  # noqa: BLE001  (one unreadable round never costs the match)
            print(f"  skipped {f.name}: {type(e).__name__}: {e}", file=sys.stderr)
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
    try:
        from . import update

        update.startup("heat3d_ext_r6")
    except Exception:  # an update check never stops a conversion
        pass
    if argv[:1] == ["info"]:
        if not argv[1:] or argv[1] in ("-h", "--help"):
            print("usage: heat3d-r6-replay info <replay.rec> [...]")
            print("Each round's header, map, site, players and events as JSON.")
            return 0 if argv[1:] else 2
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
    ap.add_argument("paths", nargs="*", help="replays (files, match folders, folders of matches, zips)")
    ap.add_argument("--game", help="your game folder: read its MatchReplay folder (or set HEAT3D_R6_GAME)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--loose", action="store_true", help="keep the separate files instead of a .3dheat")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)
    if not args.paths:
        from .install import replay_folder

        found = replay_folder(args.game)
        if found is None:
            print("name the replays, or your game folder with --game <folder> (its MatchReplay folder is read)",
                  file=sys.stderr)
            return 1
        print(f"reading {found}", file=sys.stderr)
        args.paths = [str(found)]
    out = Path(args.out)
    plain = [p for p in args.paths if not p.lower().endswith(".zip")]
    groups = _matches(plain)
    done = 0
    for z in (p for p in args.paths if p.lower().endswith(".zip")):
        with zipfile.ZipFile(z) as zf:
            for res in _zip_matches(zf, out, args.loose):
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
