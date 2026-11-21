---
title: Before you start
nav_order: 2
---

# Before you start

## The standalone program (no Python needed)

Each [release](https://github.com/Holdi601/3DHeat-Ext-R6/releases/latest)
has a ready-to-run program for Windows (`heat3d-r6-<version>-windows-x64.zip`)
with a `SHA256SUMS` file to check the download. Unpack it anywhere and start
`heat3d-r6.exe`.

Started without arguments it opens a window that:

- asks for your game folder (*Choose folder...*, the one holding
  `MatchReplay`); nothing is searched for;
- says what is missing (the game folder, free disk space);
- converts the matches in that `MatchReplay` folder, or any folder you pick,
  into `.3dheat` files (by default into `%LOCALAPPDATA%\3DHeat\matches\r6siege`);
- checks for updates and asks before installing one, unless you tick
  *Update automatically*.

The same program runs every command below:
`heat3d-r6 heat3d-r6-replay --game "<your game folder>" -o matches`.
For scripts: `heat3d-r6 --check --json` says what is found and missing, and
`heat3d-r6 status --json` the game folder found (a replay reader has no maps;
`extract` has nothing to do). The 3DHeat app's Extractors panel installs,
updates and starts it for you.

## 1. Python

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
(tick "Add python.exe to PATH"). Then, in the folder of this tool:

```text
pip install -e .
```

That installs the `heat3d-r6-replay` command. Check it with
`heat3d-r6-replay --version`.

## 2. The replays

Siege keeps your last matches in the folder `MatchReplay` inside the game's
folder. Pass your game folder with `--game "<your game folder>"` (or set
`HEAT3D_R6_GAME` to it once) and the tool reads that `MatchReplay` folder, or
name the replays yourself (see [Replays](replays.md)). Nothing is searched
for.

The game does not have to run, and should not: the tool only reads the files.

## 3. Where the files go

| What | Where | Size |
|---|---|---|
| matches | the folder you give with `-o` | 5-20 MB per match |

## 4. The maps (optional)

For the matches to stand on the real building, build the maps with the
separate tool [3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)
(`heat3d-r6-maps`) and load a map's level once in the viewer.
