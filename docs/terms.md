---
title: Terms and licence
nav_order: 8
---

# Terms and licence

This page says what this tool reads, what it does and does not do, and what
it writes.

## The replays

Match Replays are files the game writes for you to watch your own matches
again; tournament organisers publish theirs for download. The tool reads them
from disk and works out their layout from the files themselves (the header
and event markers follow what [r6-dissect](https://github.com/redraskal/r6-dissect),
MIT, documents; its code is not used).

Nothing from the game is shipped with this tool or its documentation: no
game assets, no game code, no DLLs.

**Not a cheat.** The tool never runs with the game, never reads its memory,
never touches its anti-cheat or its network traffic, and changes nothing in
the game folder. It works on files, after the match.

## What the tool does and does not do

| Does | Does not |
|---|---|
| read replay files, read-only | start, change or patch the game |
| read the `MatchReplay` folder of the game folder you name | read the game's memory, its anti-cheat or its network traffic |
| write matches on your machine | upload, publish or share anything |

## Your matches

Matches made from your own replays are yours. For replays a tournament
organiser published, follow their terms when you share anything made from
them.

## The maps

Building the maps as 3D levels reads the game's own archives; that is the
separate tool [3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps),
with its own Terms page.

## Its own project

Each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

## This tool's licence

MIT (see `LICENSE`). What it reads and what it ships is listed in
[`LICENSES.md`](https://github.com/Holdi601/3DHeat-Ext-R6/blob/main/LICENSES.md).

## Notice and contact

This project is not affiliated with or endorsed by Ubisoft. Rainbow Six Siege
and related names and trademarks belong to their owners. Rights holders: open an issue at
[github.com/Holdi601/3DHeat-Ext-R6/issues](https://github.com/Holdi601/3DHeat-Ext-R6/issues) -
we respond quickly and remove anything on request.
