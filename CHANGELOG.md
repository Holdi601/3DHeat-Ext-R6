# Changelog

## 0.7.0

- Its own icon: the 3DHeat cube with a text badge for its game (letters in 3DHeat's colours), as the
  program, window, taskbar and docs icon.
- A new window: the 3DHeat look in dark and light (follows the system, switchable), the logo and
  icon, sharp at any display scaling. Four steps: find the game (each requirement with its fix),
  choose (maps ticked when there is something to do, filters, search; jobs with their fields
  inline), work (progress, time left, cancel), done (open in 3DHeat, open the output folder, and
  for a failure what went wrong and what to do, copy details, report a problem).
- No console window on Windows: the program is a window program. From a terminal it still prints
  as before; `heat3d-r6-cli.cmd` beside it waits for it in a terminal and passes its exit code.
- The update offer in the same look: Update now / Later / Skip this version, and "Update
  automatically" from the dialog.
- CI draws every page and dialog of the window (on Linux under a virtual display) and checks the
  Windows build is a window program.
- `heat3d-r6 convert <replay>... -o <out> [--progress-json]` and `heat3d-r6 info <replay> --json` (what the
  replay says about its match, read from its header without converting it), the same verbs in every
  3DHeat replay reader; the old command lines work as before.

## 0.6.0

- A standalone program for Windows (no Python needed), built by CI with a `SHA256SUMS` file. Without
  arguments it opens a window: the game folder you choose (nothing is searched for), what is missing, and the
  conversion of its `MatchReplay` folder (or any folder) into `.3dheat` matches.
- `status --json` and `--check --json` for the 3DHeat app's Extractors panel; a replay reader has no maps, so
  `extract` has nothing to do.
- Updates ask first (update now / later / skip this version) unless automatic updates were chosen
  (`--auto-update`, the window's checkbox, or `HEAT3D_AUTO_UPDATE=1`).
- The version is written in the package (`__version__`), so the built program knows it too.
- Docs: no example install paths; you give your own folder.

## 0.5.0

- `layouts <levels folder>`: each map's bomb sites as `<level>.layouts.json` beside the levels the R6 maps tool
  wrote, every site also a stage of its own. Docs: [Replays](docs/replays.md#bomb-sites-on-the-maps).

## 0.4.1

- `info --help` prints its usage instead of trying to open a file named `--help`.
- A zip inside a bundle's zip is read too (some 2025 league bundles hold their match as one): those bundles gave no match before.
- One round the reader cannot follow is skipped with its reason, whatever the error; the match keeps its other rounds. An item tree that cannot be followed costs only that round's use rows (`items.py`), never the round.
- Installs with one pip line from the release zip, no Git needed; a pip install knows its version and updates itself with pip when a newer release is out.
- The version comes from the package's metadata when there is no VERSION file (a pip install).
- README: a quick start for new users.

## 0.4.0

- Shots, reloads, ability and gadget uses (`items.py`): `shot` (rounds fired in that tick, `count`; rounds left in all, `left`), `reload`, `ability_use` (charges used and left), `gadget_deploy` (thrown, placed, a drone going out), `gadget_destroyed`, `gadget_pickup`, each at the player's position with the item (`item`, `itemClass`). They come from each carried item's own objects (ammunition, charges left, one object per charge of a deployable), tied to the player through the inventory under the player's record.
- Where a thrown or placed gadget came to rest: `placedX`, `placedY`, `placedZ` and its track in `detail`; a gadget object that appears as its owner uses a gadget or ability is named after it (`gadgetType`, `inferred` 0.9).
- The match document's players list each player's uses (`uses`).
- The maps as 3D levels moved to their own tool and repository, [3DHeat-Ext-R6-Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps) (`heat3d-r6-maps`), with their history; this reader keeps the replays.
- With no replays named, the game's `MatchReplay` folder is found and read.
- World ids of the current map versions (read from the game's map archives).
- The updater lives in this tool's package (`heat3d_ext_r6.update`), checking Holdi601/3DHeat-Ext-R6.
- Docs: a documentation site (`docs/`: before you start, replays, terms, command reference), `LICENSES.md`.

## 0.3.0

- Room callouts (`callouts.py`): `callout` on every body sample, on the events at a player's position and, the one said most nearby, on the marks.
- Plant and defuse attempts from the defuser timer's runs: `plant_start`, `plant`, `plant_interrupted`, `defuse_start`, `defuse`, `defuse_interrupted`, with the timer as it started and stopped in `detail`. Y11 files did not name the player in these packets, so 0.2.0 found no plants there at all (and called those rounds' ends wrong); the player is now the one of the side who stood still through the attempt (`inferred` = 1).
- Reinforcements: a `reinforce` row each time the defending team's count of reinforcements left drops, at the defender who stood still through the next seconds (`inferred` = 1 / the number who did).
- Bomb sites as the match document's `objectives` (`sites.py`): each played site's rooms as floor outlines from where players stood in them, the map's other sites from `sites.json` (derived from the converted esports matches by `tools/sites_build.py`; 20 map versions, 79 sites), with the rounds and times each site was played.
- Marks: who most likely made each one (`byPlayer`, `byOperator`, `inferred` the confidence; `byItem`, `byItemClass` where that player's kill names the weapon), from the player facing the mark as it appeared. Marks no longer carry a direction: the rotation the 0.2.0 docs called the surface's normal is in the surface object's own frame.
- `track` (each body, drone and gadget its own track) and `gadgetType` (a drone; a gadget named from its owner's two deployables by whether it flew or stayed) columns.
- Positions: updates holding the object's own frame (0, 0, height) are no longer read as places (they put players at the map's origin for a tick).
- Catalogue: 205 item ids, 181 sure, 14 named by a stated fact (`RESOLVE` in `tools/catalog_build.py`), 5 weapon ids still open; a rebuild keeps the names the previous catalogue gave.
- Map names for two world ids (Fortress, Villa), told by their sites' callouts.
## 0.2.0

- Operators as picked: the operator and loadout each player has as the action phase starts, followed through the preparation phase (`loadout.py`). Before, an attacker who picked again in the preparation phase kept the operator of the recording's start.
- The catalogue (`catalog.json`, `catalog.py`): 199 item ids named from the replays (weapons, secondary gadgets, abilities, the drone), each operator's loadout (Ubisoft's operator pages), weapon classes, operator, gadget and ability roles; `tools/catalog_survey.py` and `tools/catalog_build.py` rebuild it.
- Columns: `operatorRole`, `primary`, `primaryClass`, `secondary`, `secondaryClass`, `gadget`, `gadgetRole`, `ability`, `abilityRole`, `loadout` on every row of a player; `weapon`, `weaponClass`, `weaponSlot`, `otherOperator` on kill and death rows (the kill feed's item id); `roundEndReason` and `matchWon` on every row.
- Marks on the level (`impacts.py`): bullet holes and the like as `impact` rows with their exact position, the surface's normal, the level object (`surface`) and the mark's kind (`markKind`).
- Solid Snake's operator id; Rauora and Solid Snake counted as attackers.

## 0.1.0

- First reader: header, players, operators, positions of bodies, drones and gadgets, kill feed, defuser, round clock, site, result; `.3dheat` output.