# heat3d-r6-replay

Rainbow Six Siege **Match Replays** (`.rec`, the game's "dissect" files, one a
round) into the tables the [3DHeat](https://github.com/Holdi601/3DHeat) viewer
reads: one `.3dheat` per match with every player's position tick by tick and
the room they are in, their operator and loadout, their drones and gadgets,
the kill feed with the weapon or gadget of each kill, every shot fired and
reload, every use of an ability and every gadget thrown, placed, picked up or
destroyed, every plant and defuse attempt (interrupted ones too), the
reinforcements, the marks left on the
level with who most likely made them, the bomb sites as the match's
objectives and each round's result.

Files only: the reader opens replay files on disk. It never touches the game,
its memory or its anti-cheat.

## Notice

Each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

Not affiliated with or endorsed by Ubisoft; Rainbow Six Siege and all other
trademarks belong to their owners. Meant for non-commercial, personal
analysis. Rights holders: open an issue or get in touch through the GitHub
profile; we respond within 48 hours and remove on request.

## Quick start for new users

You need: Windows, [Python](https://www.python.org/downloads/) 3.10 or later
("Add python.exe to PATH" ticked in its installer), and Match Replays: Siege
keeps your last matches in the `MatchReplay` folder inside its game folder
(for example `C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\games\Tom Clancy's Rainbow Six Siege`
or `...\steamapps\common\Tom Clancy's Rainbow Six Siege`). The tool does not
search for it: you give the game folder. No Git is needed.

1. Install the tool (one line, in PowerShell or a command prompt):

   ```bash
   python -m pip install https://github.com/Holdi601/3DHeat-Ext-R6/archive/refs/tags/v0.4.1.zip
   ```

2. Convert your recent matches (or name match folders, `.rec` files or zips
   yourself instead of `--game`; `HEAT3D_R6_GAME` can hold the game folder):

   ```bash
   heat3d-r6-replay --game "<your game folder>" -o matches
   ```

3. The output is one `.3dheat` per match in the `-o` folder, e.g.
   `matches\r6_Clubhouse_2026-01-02-20-15-00.3dheat` (5 to 20 MB).
4. Open it in the [3DHeat viewer](https://github.com/Holdi601/3DHeat#quick-start):
   download the viewer (**Code -> Download ZIP**, unpack) and double-click
   `start.bat`; it offers to install [Node.js](https://nodejs.org/) when it is
   missing and opens Chrome or Edge at `http://127.0.0.1:5273`. There,
   **Source -> Files...**, pick the `.3dheat` (or drop it on the Source panel)
   and click **Load file**. The **Match** tab has the rounds, kills and
   scoreboard. For the real building under it, build the map with
   [3DHeat-Ext-R6-Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps) and
   load its level once.

When a new release is out, the tool says so when it starts and offers to
update itself (`python -m heat3d_ext_r6.update` does the same).

## Use

```
pip install -e .
heat3d-r6-replay <file.rec | match folder | folder of matches | bundle.zip>... -o <out folder>
heat3d-r6-replay info <file.rec>        # what one round holds, as JSON
```

A match is the folder of its rounds (`Match-<date>-<id>/Match-...-R01.rec`).
The esports bundles (zips) are read in place. `--loose` keeps the separate
files instead of the `.3dheat` container.

Where replays are: the game writes them to `MatchReplay\` in its game folder,
the last 12 matches. `--game <your game folder>` reads that folder (or name
the replays yourself).

**Load in the viewer:** open the `.3dheat` in 3DHeat (One file... -> Load). With
the map's level built (see Maps below) and loaded once, the viewer puts it
under the match by itself.

## What is read

| Data | Where in the file | Notes |
|---|---|---|
| map, mode, version, teams, score, round number | header strings | `worldid` named by `game.py` |
| players, spawn | each player's record | |
| operator and loadout as the action phase starts | player records and item objects, followed through the preparation phase (`loadout.py`) | primary, secondary, secondary gadget, ability, drone: item ids named by the catalogue |
| positions, x y z in metres, Z up, facing | object stream, every tick (~30-40 a second) | operator body, attackers' drones, gadgets (owner known, type not) |
| kills, deaths, headshots, the weapon or gadget of each kill | kill feed in the event section | with the tick, so at the killer's and victim's positions |
| defuser plant / disable: start, done, interrupted | the defuser timer's runs of packets (`round._attempts`) | at the planter's or defuser's position; an attempt that stops before the timer runs out is `plant_interrupted` / `defuse_interrupted`, with the time it had left. The player is named by the packet in older seasons; in Y11 files it is not, and the player is the one of the side who stood still through the attempt, on the site (`inferred` = 1) |
| room callouts ("2F CCTV Room") | the location field of small per-player objects in the event section (`callouts.py`) | `callout` on every body sample and on the events at a player's position; marks get the callout said most near them |
| reinforcements | the defending team's count of reinforcements left (`round._reinforcements`) | a `reinforce` row when the count drops, at the defender who stood still through the next seconds (`inferred` = 1 / the number of defenders who did); none where nobody did |
| round clock (preparation, action) | clock packets | gives every tick its time; pauses squeeze out |
| winner, how, match result | header scores and the events | `won`, `roundEndReason`, `matchWon` on every row |
| site | site packets | on every row of the round |
| bomb sites | the rooms' callouts and where players stood in them (`sites.py`), the table `sites.json` | the match document's `objectives`: each played site's two rooms as floor outlines, the map's other sites from the table, with the rounds and times each was played |
| shots, reloads, ability and gadget uses | the item tree of the snapshot and the event section (`items.py`): each carried item's slot holds its ammunition (rounds in the magazine, in all, reloading), its charges left, and one object per charge of a deployable (carried, out, gone) | `shot` (rounds fired in that tick), `reload`, `ability_use`, `gadget_deploy`, `gadget_destroyed`, `gadget_pickup`, at the user's position; a thrown or placed gadget's object, where one appears as it is used, gives where it came to rest |
| marks on the level (bullet holes and the like) | a tick-indexed section of records (`impacts.py`) | exact position, the level object it sits on, the mark's kind; the shooter where one player faced the mark as it appeared (`byPlayer`, with a confidence) |

Every other moving object (doors, debris...) goes to the `entities` sidecar
with its id, tick and position.

## Columns

Every row: `time`, `x`, `y`, `z`, `yaw` (degrees from +X, counter-clockwise),
`dirX/Y/Z`, `player`, `team`, `teamName`, `side` (attack/defense), `round`,
`roundTime`, `clock`, `phase` (prep/action/planted/end), `site`, `won` (the
row's side won the round), `roundEndReason` (elimination, defuser disabled,
defuser detonated, elimination after plant, time), `matchWon` (1 won, 0 lost,
0.5 drawn), `teamAlive`, `enemyAlive`, `state_planted`, `event`, `pawn`
(operator/drone/gadget/mark), `callout` (the room, as the game names it;
empty outside named rooms), `track` (each object its own track: the body is
the player's name, a drone or gadget `<player> drone|gadget <round>.<n>` in
the order they appear), `inferred`, `detail`, `entity`.

`inferred` says how sure a worked-out value is, 0 to 1, empty where nothing
was worked out: on attempts and reinforcements the player, on marks the
shooter, on gadget rows the gadget's type.

Drone and gadget rows: `gadgetType`, what the object is. A drone is the
drone (sure). A gadget is one of its owner's two deployables (secondary
gadget and ability), told by how it moved: one that flew is the thrown one,
one that stayed the placed one (`inferred` 0.6-0.7); where both are placed
the two names are joined with ` / `.

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
level object's id; `entity` holds it too), `markKind`, `callout`, and who
most likely made it: `byPlayer`, `byOperator`, `inferred` (the confidence),
and `byItem` / `byItemClass` where that player's kill within 1.5 s names the
weapon. The shooter is the player facing the mark as it appeared (heading
within 2 degrees, or 0.4 m to the side at the mark's distance). Checked on a
pro match: 89% of the marks have such a player, but with the marks' times
moved by 7 s 22% still do, so about one attribution in four is a player who
merely faced that way; two players facing it halve the confidence. Marks
have no direction: their rotation is in the surface object's own frame,
which the file does not place (`impacts.py`).

Attempt rows (`plant_start`, `plant`, `plant_interrupted`, `defuse_start`,
`defuse`, `defuse_interrupted`): `detail` holds the timer as it started and
as it stopped (`{"of": 7.0, "left": 2.05}`). Reinforcement rows (`reinforce`):
`detail` holds the team's reinforcements left.

Use rows (`shot`, `reload`, `ability_use`, `gadget_deploy`,
`gadget_destroyed`, `gadget_pickup`; `items.py`): `item` (the weapon, gadget,
ability or drone, named by the catalogue), `itemClass` (the weapon's class,
else gadget / ability / drone), `count` (rounds fired, or charges used, in
that tick), `left` (rounds left in all after a shot, charges left after an
ability use counted from the charges), `placedX/Y/Z` (where the thrown or
placed object came to rest: its last place) and `detail` `{"object": <its
track>}` where the object is in the stream. A gadget object that appears
(up to about 4 s before, 1 s after) as its owner uses a gadget or ability is
named after it on its own rows (`gadgetType`, `inferred` 0.9); a drone's
`gadget_deploy` is the moment its object appears.

Events: `position`, `drone`, `gadget`, `kill`, `death`, `plant_start`,
`plant`, `plant_interrupted`, `defuse_start`, `defuse`, `defuse_interrupted`,
`reinforce`, `round_end`, `impact`, `shot`, `reload`, `ability_use`,
`gadget_deploy`, `gadget_destroyed`, `gadget_pickup`.

## Shots, abilities and gadgets

Each carried item is a small tree of objects in the snapshot and the event
section (`items.py`): the slot, a holder with the item object (its item id),
the ammunition object (rounds in the magazine, rounds in all, reloading) and,
for a deployable, one object per charge whose state is carried, out (placed,
thrown, deployed) or gone (used up, set off, destroyed). The slots hang under
the player's inventory, which hangs under the player's record, so each use is
tied to its player by the file itself. A drop of the rounds in all is that many shots; a
charge going out is a deploy, coming back a pick-up, gone after being out a
destruction. Items without per-charge objects (most abilities) count their
charges left, written only once they change: the first value written is one
use when the item was in hand just before.

Checked on a pro match (8 rounds): 3,652 shots, 343 reloads, 223 ability
charges and 166 deploys (82 of them drones); the per-player gadget deploys
agree with each team's count of that gadget left in 46 of 53 cases; in the
others the team's count also drops when a carrier dies. Shots have no
direction or target here: what a shot hit is not read.

## Bomb sites

The match document (`<match>.match.json`) lists the bomb sites as
`objectives`, the way the viewer reads War Thunder's capture zones: per room
`{"type": "bomb_site", "name": "B Church", "site": "B Church, B Arsenal Room",
"shape": "outline", "points": [[x, y, z]...], "position", "radius", "rounds",
"active": [[from, to]...]}` (`active`: the table's seconds of the rounds it was
played). A room's outline is the hull of where players stood while their
callout named it (the outermost 3% dropped), on its floor. A site of the map
that nobody walked into in the match is drawn from `heat3d_ext_r6/sites.json`
as a circle (`shape` `cylinder`, `from` `table`).

`sites.json` is derived from the converted esports matches
(`tools/sites_build.py survey <folder> <survey.jsonl>`, then `build`): per map
version (`worldid`) each site with English callouts, the median of the plants
made there (else of the defenders late in the preparation phase), floor
height and spread. Derived coordinates only, no game asset. 20 map versions,
79 sites; the converted matches it was built from were mostly written by 0.1.0,
which missed Y11 plants, so most sites come from the defenders.

## The catalogue

`heat3d_ext_r6/catalog.json` names the item ids the replays use (205 ids:
weapons, secondary gadgets, abilities, the drone), with each operator's
loadout from Ubisoft's operator pages and weapon classes; `catalog.py` adds
roles (an operator's usual job, a gadget's or ability's purpose: this
project's classification). The ids are named from the replays themselves: an
id is the weapon or gadget that the loadouts of all operators carrying it
share (`tools/catalog_survey.py` lists who carries what over many rounds,
`tools/catalog_build.py` names them). Each id says how sure that is:

- `sure`: one name fits the operators carrying it (181 ids, from 734 rounds
  of 2024-2026 esports replays).
- `by`: named by a further fact, which `by` states (14 ids): the headshot
  share of its kills (a shotgun against a rifle), another operator carrying
  the same id (Flores's T-95 LSW is Ying's too), the operator's other weapon
  being named already, or the id's range (a weapon from the game's launch
  keeps its launch-era id, 1366019xxx, for everyone carrying it; a weapon
  added with an operator gets an id of that season). These facts and their
  reasons are `RESOLVE` in `tools/catalog_build.py`.
- otherwise `candidates`: the names that fit; the table shows them joined
  with ` / `. Still open: Gridlock's two primaries (F90 / M249 SAW: both
  rifles, the headshot share does not tell), two of Jackal's (C7E / ITA12L /
  PDW9) and one of Caveira's (M12 / SPAS-15), each seen in a few rounds; one
  ability id seen in 3 rounds with no carrier named.

A rebuild keeps the names the previous catalogue gave and lists where the
bigger survey's slot vote disagrees (four ids: a breach charge or claymore,
Jäger's ADS or an observation blocker, a bulletproof camera or nitro cell,
Frost's Super 90 or 9mm C1, whose headshot share is 39% of 33 kills).

Loadouts change with seasons; the operator pages are those of 2026-11. Not in
the catalogue: weapon damage, fire rate and magazine size, operator speed and
health (they change with balance patches; no official text source was used,
so none is guessed). No game assets (icons, models, textures) are used or
shipped.

## Not read (yet)

Attachments (the weapon's record holds small numbers, not named ids), health
and damage, the size of a hole's opening, walls and floors opened, which wall
or hatch a reinforcement went on and whether it was breached later,
barricades on doors and windows (a section of level objects with health
values and positions holds them, not decoded yet), stance (standing,
crouching, prone) and leaning (not found yet: the body's updates, the
per-body state values of another section and the event section's
per-player toggles were checked against the players' speeds, none
separates), camera use. Online
profile ids are read but kept out of the output on purpose.

Found but not used: each team's count of each secondary gadget left
(`66 6b 18 44`, with the item id under `e5 86 a6 c5`): it also drops when a
carrier dies, so the uses come from each player's own slot instead.

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

## Maps

The maps as 3D levels, for these matches to stand on, come from the separate
tool [3DHeat-Ext-R6-Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)
(`heat3d-r6-maps`), which builds them from your own installed game. Its levels
name each breakable object by the same level-object id this reader gives a
mark's `surface`, and the map version by the same world id.

Documentation: `docs/` (published as the project's site): before you start,
replays, terms, command reference.

The Watcher (3DHeat-Watcher) can later call this tool for new MatchReplay
files as an optional step; not wired yet.

## Licence

MIT. Replays and game files are not included and never committed; see
`LICENSES.md`.
