---
title: Before you start
nav_order: 2
---

# Before you start

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
