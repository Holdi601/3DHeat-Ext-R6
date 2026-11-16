---
title: Home
nav_order: 1
---

# 3DHeat R6

**What is it?** A tool for Rainbow Six Siege and the
[3DHeat](https://github.com/Holdi601/3DHeat) viewer
([documentation](https://holdi601.github.io/3DHeat/)). Siege records your
matches as *Match Replays* (`.rec` files, one per round). The tool reads them
and writes one `.3dheat` file per match: where every player was, tick by tick,
their operators and loadouts, kills, plants and defuses, and how each round
ended. See [Replays](replays.md).

**Why would I use it?** To see where a team stood, moved and fought. With the
map as a 3D level from the separate tool
[3DHeat R6 Maps](https://github.com/Holdi601/3DHeat-Ext-R6-Maps)
(`heat3d-r6-maps`), the viewer shows it on the real building, floor by floor.

**Example:**

```text
heat3d-r6-replay --game "<your game folder>" -o matches   # your recent matches -> matches/r6_<Map>_<date>.3dheat
```

Then open the `.3dheat` in the viewer (**One file…**, then **Load**).

**What you need:** Python 3.10 or newer - see
[Before you start](before-you-start.md).

**What it never does:** start or touch the game, its anti-cheat or its memory;
upload or share anything. See [Terms and licence](terms.md).

**Its own project:** each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

**Notice:** not affiliated with or endorsed by Ubisoft; Rainbow Six Siege and
related names and trademarks belong to their owners. Rights holders: open an issue at
[github.com/Holdi601/3DHeat-Ext-R6/issues](https://github.com/Holdi601/3DHeat-Ext-R6/issues) -
we respond quickly and remove anything on request.

| Page | What it covers |
|---|---|
| [Before you start](before-you-start.md) | installing, where the replays are, where the files go |
| [Replays](replays.md) | turning Match Replays into `.3dheat` matches |
| [Terms and licence](terms.md) | what this tool reads, does and does not do, and writes |
| [Command reference](cli-reference.md) | every option, generated from the program |
