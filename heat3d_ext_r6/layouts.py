"""
Each map's bomb sites as a 3DHeat layout, for the maps the R6 maps tool (3DHeat-Ext-R6Maps) wrote: one layout
`bomb` with every site of the map, each site also a stage of its own (named by its two rooms), from the sites
table (`sites.py`, `sites.json`: derived coordinates only).

A level's `.json` (beside its `.glb`) names its map version (`world_id`); a version the table does not hold takes
the map's newest that it does. Positions are the level's frame: the .glb holds the replays' (x, z, y).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sites import table

FORMAT = "3dheat-layouts"


def _sites(world_id: str, map_name: str) -> tuple[str, dict[str, dict]]:
    maps = table()
    if world_id in maps:
        return world_id, maps[world_id].get("sites", {})
    same = [(k, v) for k, v in maps.items() if (v.get("map") or "").lower() == map_name.lower()]
    if not same:
        return "", {}
    # The newest version: the one with the latest season named, else the most rounds.
    same.sort(key=lambda kv: (max(kv[1].get("versions") or [""]), sum(s.get("rounds", 0) for s in kv[1]["sites"].values())))
    return same[-1][0], same[-1][1].get("sites", {})


def level_layouts(meta: dict[str, Any], level: str, tool: str) -> dict[str, Any] | None:
    """A level's layouts from its .json; None when the table knows no site of its map."""
    used, sites = _sites(str(meta.get("world_id") or ""), str(meta.get("map") or ""))
    if not sites:
        return None
    names = sorted(sites)
    objectives = []
    for i, site in enumerate(names):
        s = sites[site]
        objectives.append({"type": "bomb_site", "name": site, "site": site, "team": None, "shape": "cylinder",
                           "position": [s["x"], s["z"], s["y"]], "radius": s["r"], "height": 2.5,
                           "stage": i + 1, "from": s.get("from", ""), "rounds": s.get("rounds", 0)})
    return {"format": FORMAT, "version": 1, "game": "r6", "level": level, "map": meta.get("map"),
            "worldId": used, "source": tool, "units": "m", "up": "y",
            "coordinates": "the level's frame: the replays' (x, z, y)",
            "layouts": [{"id": "bomb", "name": "Bomb", "mode": "bomb", "aliases": ["secure", "hostage", "ranked"],
                         "stageNames": {str(i + 1): n for i, n in enumerate(names)},
                         "objectives": objectives, "zones": [], "spawns": []}]}


def write_all(folder: Path, tool: str) -> list[str]:
    """Every level in `folder` (a `<level>.json` the maps tool wrote beside its `.glb`) gets its layouts."""
    out = []
    for meta_path in sorted(folder.glob("*.json")):
        if meta_path.name.endswith(".layouts.json") or not meta_path.with_suffix(".glb").exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("game") != "r6siege":
            continue
        doc = level_layouts(meta, meta_path.stem, tool)
        if doc is None:
            out.append(f"{meta_path.stem}: no sites known for {meta.get('map')}")
            continue
        dest = meta_path.with_name(f"{meta_path.stem}.layouts.json")
        dest.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        out.append(f"ok {dest} {len(doc['layouts'][0]['objectives'])} sites")
    return out
