"""The standalone spec on a synthetic game folder (tiny fake files, no game data)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from heat3d_ext_r6 import standalone_spec
from heat3d_ext_r6.app import entry, paths, update
from heat3d_ext_r6.app import spec as app_spec


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))
    monkeypatch.setenv("HEAT3D_LEVELS", str(tmp_path / "levels"))
    monkeypatch.setenv("HEAT3D_NO_UPDATE", "1")
    monkeypatch.delenv("HEAT3D_R6_GAME", raising=False)
    update.AUTO_THIS_RUN = False


def game(tmp_path: Path) -> Path:
    g = tmp_path / "game"
    (g / "MatchReplay" / "Match-2026-01-01_00-00-00-1").mkdir(parents=True)
    (g / "MatchReplay" / "Match-2026-01-01_00-00-00-1" / "Match-R01.rec").write_bytes(b"x")
    return g


def run(*argv, capsys):
    code = entry.main(standalone_spec.SPEC, list(argv))
    return code, capsys.readouterr().out


def test_find_only_the_folder_given(tmp_path, monkeypatch):
    g = game(tmp_path)
    find = standalone_spec.SPEC.games[0].find
    assert find(None) is None  # nothing is searched for
    assert find(str(tmp_path)) is None
    assert find(str(g)) == g
    monkeypatch.setenv("HEAT3D_R6_GAME", str(g))
    assert find(None) == g


def test_task_reads_the_chosen_folder(tmp_path):
    g = game(tmp_path)
    app_spec.save_settings("heat3d-r6", {"games": {"r6siege": str(g)}})
    task = standalone_spec.SPEC.tasks[0]
    src, out = task.inputs
    levels = tmp_path / "levels"
    assert src.default(levels) == str(g / "MatchReplay")
    assert out.default(levels) == str(paths.data_dir() / "matches" / "r6siege")
    argv = task.argv({"src": src.default(levels), "out": "o"}, levels)
    assert argv == ["heat3d-r6-replay", str(g / "MatchReplay"), "-o", "o"]
    assert argv[0] in standalone_spec.SPEC.tools


def test_no_maps_nothing_to_extract(tmp_path, capsys):
    g = game(tmp_path)
    app_spec.save_settings("heat3d-r6", {"games": {"r6siege": str(g)}})
    _, out = run("status", "--json", capsys=capsys)
    doc = json.loads(out)
    assert doc["games"][0]["found"] and doc["games"][0]["maps"] == []
    code, out = run("extract", "--new", "--progress-json", capsys=capsys)
    assert code == 0 and json.loads(out.splitlines()[-1]) == {"event": "done", "ok": 0, "failed": 0}
