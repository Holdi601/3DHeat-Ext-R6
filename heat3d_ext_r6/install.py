"""
The replay folder of the installation you name.

Nothing is searched for: with `--game <your game folder>` (or `HEAT3D_R6_GAME`)
the tool reads that folder's `MatchReplay` subfolder, where the game keeps
your last matches.
"""

from __future__ import annotations

import os
from pathlib import Path


def replay_folder(given: str | os.PathLike[str] | None = None) -> Path | None:
    """`MatchReplay` inside the folder given (or in `HEAT3D_R6_GAME`), or None."""
    chosen = given or os.environ.get("HEAT3D_R6_GAME")
    if not chosen:
        return None
    for name in ("MatchReplay", "matchreplay"):
        p = Path(chosen) / name
        if p.is_dir():
            return p
    return None
