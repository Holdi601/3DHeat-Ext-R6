"""A match survives what the reader cannot follow: item trees that fail, a zip inside the bundle's zip."""

from __future__ import annotations

import io
import zipfile

import zstandard

from heat3d_ext_r6 import cli, items, rec, round as rnd
from test_rec import _body, _header


def _rec_bytes() -> bytes:
    return _header() + zstandard.ZstdCompressor().compress(_body())


def test_a_failing_item_tree_costs_only_the_use_rows(tmp_path, monkeypatch, capsys):
    f = tmp_path / "Match-R01.rec"
    f.write_bytes(_rec_bytes())

    def broken(*_a, **_k):
        raise KeyError("no slot")

    monkeypatch.setattr(items, "read", broken)
    rd = rnd.read_round(rec.read(f))
    assert rd.uses == [] and rd.map == "Clubhouse"
    assert "item uses not read" in capsys.readouterr().err


def test_a_zip_inside_the_bundle(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("2. A VS B/Match-2026-01-01_00-00-00-1/Match-2026-01-01_00-00-00-1-R01.rec", _rec_bytes())
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as z:
        z.writestr("2. A VS B.zip", inner.getvalue())
    out = tmp_path / "out"
    assert cli.main([str(bundle), "-o", str(out), "--loose"]) == 0
    assert list(out.glob("*.parquet"))
