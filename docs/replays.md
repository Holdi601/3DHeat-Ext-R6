---
title: Replays
nav_order: 3
---

# Replays into matches

Siege keeps your last matches as *Match Replays* in the folder `MatchReplay`
inside the game's install folder: one folder per match, one `.rec` file per
round (`Match-<date>-<id>/Match-<date>-<id>-R01.rec`). Tournament organisers
also publish replays as zip files.

## Your own matches

```text
heat3d-r6-replay --game "<your game folder>" -o matches
```

reads the `MatchReplay` folder inside the game folder you name and converts
every match in it. Each match becomes one file:

```text
matches/r6_Clubhouse_2026-01-02-20-15-00.3dheat
```

## Other replays

```text
heat3d-r6-replay "D:\Replays\Match-2026-01-02_20-15-00-123" -o matches     # one match folder
heat3d-r6-replay "D:\Replays" -o matches                                    # every match below a folder
heat3d-r6-replay "D:\Downloads\tournament-day-1.zip" -o matches             # a zip, read in place
heat3d-r6-replay info "D:\Replays\Match-...\Match-...-R01.rec"              # what one round holds
```

## In the viewer

1. Open the viewer and pick the `.3dheat` file (**One file…**), then **Load**.
2. The heat of every player appears. With the map's level loaded once (made
   by the separate tool [3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)),
   the viewer puts it under the match by itself.
3. The **Match** tab has the rounds, kills and scoreboard; the replay plays
   the players as figures.

## What is in a match

Every player's position and facing (30-40 times a second), operator and
loadout, drones and gadgets, the kill feed with weapons and headshots, every
plant and defuse attempt, reinforcements, the bomb sites, the room each
player is in, the marks bullets leave on walls (with the level object they sit
on), and each round's result. The full list of columns is in the
[README](https://github.com/Holdi601/3DHeat-Ext-R6#columns).

A recording made by a player (not a spectator) may only hold what that
player's game was told: enemies out of sight can be missing.
