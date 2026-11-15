# heat3d-r6-replay

Rainbow Six Siege **Match Replays** (`.rec`, the game's "dissect" files, one a
round) into the tables the [3DHeat](https://github.com/Holdi601/3DHeat) viewer
reads: one `.3dheat` per match with every player's position tick by tick,
their operator and loadout, their drones and gadgets, the kill feed with the
weapon or gadget of each kill, the defuser, the marks left on the level and
each round's result.

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
| players, spawn | each player's record | |
| operator and loadout as the action phase starts | player records and item objects, followed through the preparation phase (`loadout.py`) | primary, secondary, secondary gadget, ability, drone: item ids named by the catalogue |
| positions, x y z in metres, Z up, facing | object stream, every tick (~30-40 a second) | operator body, attackers' drones, gadgets (owner known, type not) |
| kills, deaths, headshots, the weapon or gadget of each kill | kill feed in the event section | with the tick, so at the killer's and victim's positions |
| defuser plant / disable (start and done) | defuser timer packets | at the planter's or defuser's position |
| round clock (preparation, action) | clock packets | gives every tick its time; pauses squeeze out |
| winner, how, match result | header scores and the events | `won`, `roundEndReason`, `matchWon` on every row |
| site | site packets | on every row of the round |
| marks on the level (bullet holes and the like) | a tick-indexed section of records (`impacts.py`) | exact position, the surface's normal, the level object it sits on, the mark's kind |

Every other moving object (doors, debris...) goes to the `entities` sidecar
with its id, tick and position.

## Columns

Every row: `time`, `x`, `y`, `z`, `yaw` (degrees from +X, counter-clockwise),
`dirX/Y/Z`, `player`, `team`, `teamName`, `side` (attack/defense), `round`,
`roundTime`, `clock`, `phase` (prep/action/planted/end), `site`, `won` (the
row's side won the round), `roundEndReason` (elimination, defuser disabled,
defuser detonated, elimination after plant, time), `matchWon` (1 won, 0 lost,
0.5 drawn), `teamAlive`, `enemyAlive`, `state_planted`, `event`, `pawn`
(operator/drone/gadget/mark), `detail`, `entity`.

What the player plays and carries in the round, on all of their rows:
`operator`, `operatorRole`, `primary`, `primaryClass`, `secondary`,
`secondaryClass`, `gadget`, `gadgetRole`, `ability`, `abilityRole` and
`loadout` (the four joined with `|`, one breakdown factor each).

Kill and death rows: `weapon` (what the kill was made with: the death row
names the killer's weapon, as in the CS2 tables), `weaponClass` (assault
rifle, smg, shotgun, dmr, lmg, handgun, machine pistol, hand cannon, shield,
or gadget / ability), `weaponSlot` (primary, secondary, gadget, ability),
`other` (the victim or killer), `otherOperator`, `headshot`.

Mark rows (`event` = `impact`, `pawn` = `mark`, no player): `surface` (the
level object's id; `entity` holds it too), `markKind`, and `dirX/Y/Z` = the
surface's normal at the mark.

Events: `position`, `drone`, `gadget`, `kill`, `death`, `plant_start`,
`plant`, `defuse_start`, `defuse`, `round_end`, `impact`.

## The catalogue

`heat3d_ext_r6/catalog.json` names the item ids the replays use (199 ids:
weapons, secondary gadgets, abilities, the drone), with each operator's
loadout from Ubisoft's operator pages and weapon classes; `catalog.py` adds
roles (an operator's usual job, a gadget's or ability's purpose: this
project's classification). The ids are named from the replays themselves: an
id is the weapon or gadget that the loadouts of all operators carrying it
share (`tools/catalog_survey.py` lists who carries what over many rounds,
`tools/catalog_build.py` names them). Each id says how sure that is:

- `sure`: one name fits the operators carrying it (165 ids).
- `by: headshot share of its kills`: a weapon only one operator carries, one
  of two candidates a shotgun, told apart by the headshot share of its kills
  (11 ids).
- otherwise `candidates`: the names that fit; the table shows them joined
  with ` / ` (for instance `AUG A2 / MP5K`).

Loadouts change with seasons; the operator pages are those of 2026-11. Not in
the catalogue: weapon damage, fire rate and magazine size, operator speed and
health (they change with balance patches; no official text source was used,
so none is guessed). No game assets (icons, models, textures) are used or
shipped.

## Not read (yet)

Attachments (the weapon's record holds small numbers, not named ids), health
and damage, shots, what each placed gadget object is, who made a mark on the
level and the size of the opening, walls and floors opened, reinforcements,
barricades and hatches (a section of level objects with health values and
positions holds them, not decoded yet), camera use. Online profile ids are
read but kept out of the output on purpose.

The marks' `surface` ids are the map's own: they keep their value across the
matches of one version of a map (a rework gives the map a new `worldid` and
new ids).

## Seasons

Verified on Y9S1 to Y11S3 replays (2024-2026 esports bundles). The event
markers and their per-season offsets (Y7 to Y10) follow what r6-dissect
documents; the object stream (positions), the loadouts and the marks were
worked out on Y9-Y11 files.

## How the format was worked out

The header strings, the event markers and the operator and map ids follow
[r6-dissect](https://github.com/redraskal/r6-dissect) (MIT), studied and
credited; no code of it is used. The section and block framing, the tick
index shared by all sections, the object packets with their positions, the
owner id in each object's first update, the millisecond round clock, the
player records and item objects, the kill feed's item field and the mark
records were worked out here from the files. See `heat3d_ext_r6/rec.py`,
`round.py`, `loadout.py` and `impacts.py`.

## Licence

MIT. Replays are not included and never committed.
