"""
The standalone app's description of this tool (app/spec.py): the game folder
you name (nothing is searched for), whose `MatchReplay` folder holds your last
matches, and their conversion as a task. A replay reader has no maps (they
come from heat3d-r6-maps). `python -m heat3d_ext_r6.standalone_spec` runs the
app from a checkout; the release executable runs the same.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import __version__
from .app import paths
from .app.spec import GameSpec, Input, Replays, Spec, Task, load_settings

TOOL_ID = "heat3d-r6"


def _chosen(given: str | None = None) -> str | None:
    if given:
        return given
    games = load_settings(TOOL_ID).get("games")
    return (games.get("r6siege") if isinstance(games, dict) else None) or os.environ.get("HEAT3D_R6_GAME") or None


def _find(given: str | None) -> Path | None:
    from .install import replay_folder

    chosen = _chosen(given)
    return Path(chosen) if chosen and replay_folder(chosen) else None


def _replays(levels: Path) -> str:
    from .install import replay_folder

    folder = replay_folder(_chosen())
    return str(folder) if folder else ""

def _replay_info(path: Path) -> dict:
    """`info <replay> --json`: the header only (replay_info.py)."""
    from .replay_info import info

    return info(path)


SPEC = Spec(
    id=TOOL_ID,
    name="3DHeat R6",
    repo="Holdi601/3DHeat-Ext-R6",
    version=__version__,
    tools={"heat3d-r6-replay": "heat3d_ext_r6.cli:main"},
    default_tool="heat3d-r6-replay",
    description="Rainbow Six Siege Match Replays into matches for the 3DHeat viewer",
    module="heat3d_ext_r6.standalone_spec",
    games=[GameSpec(key="r6siege", label="Rainbow Six Siege", find=_find, platforms=("windows-x64",))],
    tasks=[Task(
        "replays", "Convert Match Replays",
        [Input("src", "Folder with match replays (MatchReplay in your game folder)", "folder", default=_replays),
         Input("out", "Where the matches go", "folder",
               default=lambda levels: str(paths.data_dir() / "matches" / "r6siege"))],
        lambda v, levels: ["heat3d-r6-replay", v["src"], "-o", v["out"]],
        help="each match becomes one .3dheat file the viewer opens; the maps come from heat3d-r6-maps",
    )],
    min_free_gb=1.0,
    replays=Replays("r6", (".rec",), lambda r, out: ["heat3d-r6-replay", str(r), "-o", str(out)], info=_replay_info),
    notice="Not affiliated with or endorsed by Ubisoft.",
)

if __name__ == "__main__":
    from . import update
    from .app.entry import main

    raise SystemExit(main(SPEC, apply_source=update.apply))
