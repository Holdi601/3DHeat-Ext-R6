# Licences and what this tool touches

This package is MIT licensed (see `LICENSE`). It ships code only.

## What it reads

**Match replays** (`.rec`) that the game wrote on your machine, in its
`MatchReplay` folder, or that a tournament organiser published for download.
They are read in place and never sent anywhere. With `--game` the tool reads
the `MatchReplay` folder inside the game folder you name; it searches for
nothing and reads nothing else of the installation.

The game is never started, and its anti-cheat, memory and network traffic are
never touched.

## What it writes

Matches (`.3dheat`) on your machine, for the 3DHeat viewer. Replays you
recorded yourself are yours to keep; for replays a tournament organiser
published, follow their terms when you share anything made from them.

## Facts, not assets

`game.py` and the catalogue files list identifiers (map ids, operator ids,
item ids and their names) gathered as facts about the game, partly from
[r6-dissect](https://github.com/redraskal/r6-dissect) (MIT), credited there,
and from Ubisoft's public operator pages (each operator's weapons and gadgets,
`tools/ubisoft-loadouts.json`). Room names and the bomb-site table
(`sites.json`) are derived from converted matches. None of them is a copy of
game data files.

## How the format was worked out

From the files themselves. r6-dissect (MIT) was studied for the replay header
and event markers; its code is not used.

## Maps

The maps as 3D levels are a separate tool with its own licence notes:
[3DHeat-Ext-R6-Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps).

## Takedown

Rainbow Six Siege is a trademark of Ubisoft. This project is not affiliated
with or endorsed by Ubisoft. If Ubisoft asks for this tool to be taken down,
it will be.
