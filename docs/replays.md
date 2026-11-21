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

## Bomb sites on the maps

`heat3d-r6-replay layouts <levels folder>` writes `<level>.layouts.json`
beside each map the R6 maps tool wrote there: the map's bomb sites from the
sites table (derived coordinates only), all together and each site as a stage
of its own. The viewer draws them on the map without a match loaded (Objectives
panel, Tactics board). A map the table holds no site of is listed and skipped.

## What is in a match

Every player's position and facing (30-40 times a second), operator and
loadout, drones and gadgets, the kill feed with weapons and headshots, every
plant and defuse attempt, reinforcements, the bomb sites, the room each
player is in, the marks bullets leave on walls (with the level object they sit
on), and each round's result. The full list of columns is in the
[README](https://github.com/Holdi601/3DHeat-Ext-R6#columns).

## Shots, abilities and gadgets

Each player's use of what they carry is an event of its own, at the player's
position and with the item's name (`item`) and class (`itemClass`):

| Event | When |
|---|---|
| `shot` | rounds were fired; `count` how many in that moment, `left` the rounds left in all |
| `reload` | a reload starts |
| `ability_use` | the operator's ability is used; `count` charges used, `left` charges left |
| `gadget_deploy` | a gadget is thrown or placed, or a drone goes out |
| `gadget_destroyed` | a placed or thrown gadget is used up, set off or destroyed |
| `gadget_pickup` | a placed gadget is picked up again |

Where the thrown or placed object can be followed, `placedX`, `placedY`,
`placedZ` give where it came to rest, and the gadget's own track is named
after it.

Stance (crouching, prone) and leaning are not in the tables yet.

A recording made by a player (not a spectator) may only hold what that
player's game was told: enemies out of sight can be missing.
