---
title: Home
nav_order: 1
---

# 3DHeat R6

**What is it?** A tool for Rainbow Six Siege and the
[3DHeat](https://github.com/Holdi601/3DHeat) viewer
([documentation](https://holdi601.github.io/3DHeat/)). Siege records your
matches as *Match Replays* (`.rec` files, one per round). The tool reads them
and writes one `.3dheat` file per match: where every player was, tick by tick,
their operators and loadouts, kills, plants and defuses, and how each round
ended. See [Replays](replays.md).

**Why would I use it?** To see where a team stood, moved and fought. With the
map as a 3D level from the separate tool
[3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)
(`heat3d-r6-maps`), the viewer shows it on the real building, floor by floor.

**Example:**

```text
heat3d-r6-replay --game "<your game folder>" -o matches   # your recent matches -> matches/r6_<Map>_<date>.3dheat
```

Then open the `.3dheat` in the viewer (**One file…**, then **Load**).

**What you need:** Python 3.10 or newer - see
[Before you start](before-you-start.md).

**What it never does:** start or touch the game, its anti-cheat or its memory;
upload or share anything. See [Terms and licence](terms.md).

**Its own project:** each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

**Notice:** not affiliated with or endorsed by Ubisoft; Rainbow Six Siege and
related names and trademarks belong to their owners. Rights holders: open an issue at
[github.com/Holdi601/3DHeat-Ext-R6/issues](https://github.com/Holdi601/3DHeat-Ext-R6/issues) -
we respond quickly and remove anything on request.

## Quick start

You need Windows, Python 3.10 or later ("Add python.exe to PATH" ticked in its
installer) and Match Replays: Siege keeps your last matches in the
`MatchReplay` folder inside its game folder, which you give; no
Git. More in [Before you start](before-you-start.md).

```bash
python -m pip install https://github.com/Holdi601/3DHeat-Ext-R6/archive/refs/tags/v0.5.0.zip
heat3d-r6-replay --game "<your game folder>" -o matches   # your recent matches
```

`HEAT3D_R6_GAME` can hold the game folder instead; match folders, `.rec` files
and zips can be named instead of `--game` ([Replays](replays.md)). The output
is one `.3dheat` per match in the `-o` folder, e.g.
`matches\r6_Clubhouse_2026-01-02-20-15-00.3dheat` (5 to 20 MB).

Then open it in the [3DHeat viewer](https://github.com/Holdi601/3DHeat#quick-start):
download it (**Code -> Download ZIP**, unpack), double-click `start.bat` (it
offers to install Node.js when it is missing and opens `http://127.0.0.1:5273`),
then **Source -> Files...**, pick the `.3dheat` (or drop it on the Source
panel) and click **Load file** ([In the viewer](replays.md#in-the-viewer)).
For the real building under it, build the map with
[3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps) and load its
level once.

When a new release is out, the tool says so when it starts and offers to
update itself (`python -m heat3d_ext_r6.update` does the same).

## Pages

| Page | What it covers |
|---|---|
| [Before you start](before-you-start.md) | installing, where the replays are, where the files go |
| [Replays](replays.md) | turning Match Replays into `.3dheat` matches |
| [Terms and licence](terms.md) | what this tool reads, does and does not do, and writes |
| [Command reference](cli-reference.md) | every option, generated from the program |
