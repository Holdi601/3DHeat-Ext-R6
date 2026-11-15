---
title: Terms and licence
nav_order: 8
---

# Terms and licence

This page says what this tool does and does not do. It is not legal advice.

## The replays

Match Replays are files the game writes for you to watch your own matches
again; tournament organisers publish theirs for download. The tool reads them
from disk and works out their layout from the files themselves (the header
and event markers follow what [r6-dissect](https://github.com/redraskal/r6-dissect),
MIT, documents; its code is not used).

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
whose Terms page quotes the game's licence on it.

## This tool's licence

MIT (see `LICENSE`). What it reads and what it ships is listed in
[`LICENSES.md`](https://github.com/Holdi601/3DHeat-Ext-R6/blob/main/LICENSES.md).
Rainbow Six Siege is a trademark of Ubisoft; this project is not affiliated
with or endorsed by Ubisoft.
