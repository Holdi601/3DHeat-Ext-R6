# heat3d-r6-replay

Rainbow Six Siege **Match Replays** (`.rec`, the game's "dissect" files, one a
round) into the tables the [3DHeat](https://github.com/Holdi601/3DHeat) viewer
reads: one `.3dheat` per match with every player's position tick by tick,
their drones and gadgets, the kill feed, the defuser and each round's result.

Files only: the reader opens replay files on disk. It never touches the game,
its memory or its anti-cheat.

## Use

```
pip install -e .
heat3d-r6-replay <file.rec | match folder | folder of matches | bundle.zip>... -o <out folder>
heat3d-r6-replay info <file.rec>        # what one round holds, as JSON
```

A match is the folder of its rounds (`Match-<date>-<id>/Match-...-R01.rec`).
The esports bundles (zips) are read in place. `--loose` keeps the separate
files instead of the `.3dheat` container.

Where replays are: the game writes them to `MatchReplay\` in its install folder
(Ubisoft Connect or Steam), the last 12 matches.

## What is read

| Data | Where in the file | Notes |
|---|---|---|
| map, mode, version, teams, score, round number | header strings | `worldid` named by `game.py` |
| players, operators, spawn | each player's block | operator as picked at the end of the preparation phase |
| positions, x y z in metres, Z up, facing | object stream, every tick (~30-40 a second) | operator body, attackers' drones, gadgets (owner known, type not) |
| kills, deaths, headshots | kill feed in the event section | with the tick, so at the killer's and victim's positions |
| defuser plant / disable (start and done) | defuser timer packets | |
| round clock (preparation, action) | clock packets | gives every tick its time; pauses squeeze out |
| winner, how | header scores and the events | `round_end` row per player with `won` |
| site | site packets | |

Every other moving object (bullets' impacts, doors, debris...) goes to the
`entities` sidecar with its id, tick and position.

## Columns

`time`, `x`, `y`, `z`, `yaw` (degrees from +X, counter-clockwise), `dirX/Y/Z`,
`player`, `team`, `teamName`, `side` (attack/defense), `operator`, `event`
(`position`, `drone`, `gadget`, `kill`, `death`, `plant_start`, `plant`,
`defuse_start`, `defuse`, `round_end`), `pawn` (operator/drone/gadget),
`other` (the victim or killer), `headshot`, `won`, `round`, `roundTime`,
`clock`, `phase` (prep/action/planted/end), `site`, `teamAlive`,
`enemyAlive`, `state_planted`, `detail`, `entity`.

## Not read (yet)

Weapons and loadouts, health and damage, shots, what each gadget is,
preparation-phase operator swaps, cameras, reinforcements and destruction.
Online profile ids are read but kept out of the output on purpose.

## Seasons

Verified on Y11S1 (2026) replays. The event markers and their per-season
offsets (Y7 to Y10) follow what r6-dissect documents; the object stream
(positions) and its tick framing were worked out on Y11S1 files only.

## How the format was worked out

The header strings, the event markers and the operator and map ids follow
[r6-dissect](https://github.com/redraskal/r6-dissect) (MIT), studied and
credited; no code of it is used. The section and block framing, the tick
index shared by all sections, the object packets with their positions, the
owner id in each object's first update and the millisecond round clock were
worked out here from the files. See `heat3d_ext_r6/rec.py` and `round.py`.

## Licence

MIT. Replays are not included and never committed.
