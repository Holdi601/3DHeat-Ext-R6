"""Bomb sites as a level's layouts (layouts.py), from the sites table."""

from heat3d_ext_r6 import layouts
from heat3d_ext_r6.sites import table


def test_a_known_map_gets_its_sites_as_stages():
    world, entry = next(iter(table().items()))
    doc = layouts.level_layouts({"world_id": int(world), "map": entry["map"]}, "r6_Test", "test")
    lay = doc["layouts"][0]
    assert len(lay["objectives"]) == len(entry["sites"]) == len(lay["stageNames"])
    site = lay["objectives"][0]
    s = entry["sites"][site["name"]]
    assert site["type"] == "bomb_site" and site["position"] == [s["x"], s["z"], s["y"]]


def test_a_newer_version_takes_the_maps_sites_and_an_unknown_map_none():
    entry = next(iter(table().values()))
    assert layouts.level_layouts({"world_id": 1, "map": entry["map"]}, "r6_Test", "test") is not None
    assert layouts.level_layouts({"world_id": 1, "map": "No Such Map"}, "r6_Test", "test") is None
