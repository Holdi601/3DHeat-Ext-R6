---
title: Command reference
nav_order: 90
---

# Command reference

Generated from the code by `tools/gen_docs_reference.py`: do not edit by hand.
The other pages explain each command step by step; the README lists every column of a match.

## `heat3d-r6-replay`

```text
usage: heat3d-r6-replay [-h] [--game GAME] -o OUT [--loose] [--version] [paths ...]

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

positional arguments:
  paths          replays (files, match folders, folders of matches, zips)

options:
  -h, --help     show this help message and exit
  --game GAME    your game folder: read its MatchReplay folder (or set HEAT3D_R6_GAME)
  -o, --out OUT
  --loose        keep the separate files instead of a .3dheat
  --version      show program's version number and exit
```

## `heat3d-r6-replay layouts`

```text
usage: heat3d-r6-replay layouts <levels folder>
Each map's bomb sites as <level>.layouts.json beside the levels the R6 maps tool wrote there.
```
