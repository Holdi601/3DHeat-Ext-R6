"""The file layout on synthetic bytes, and (marked `local`) a real round where one is on this machine."""

from __future__ import annotations

import glob
import os
import struct

import pytest
import zstandard

from heat3d_ext_r6 import rec, round as rnd


def _s(text: str) -> bytes:
    b = text.encode()
    return bytes([len(b)]) + b"\x00" * 7 + b


def _header() -> bytes:
    kv = ["playerid", "11", "playername", "alpha", "team", "1", "rolename", "MIRA",
          "version", "Y11S1", "code", "9598646", "datetime", "2026-01-01-00-00-00", "matchtype", "4",
          "worldid", "407193663917", "gamemodeid", "327933806", "roundnumber", "0",
          "teamname0", "A", "teamname1", "B", "teamscore0", "0", "teamscore1", "1",
          "startingteamscore0", "0", "startingteamscore1", "0"]
    return b"dissect\x00\x02\x00" + _s("UNKNOWN") + b"".join(_s(x) for x in kv)


def _body() -> bytes:
    # Snapshot region, then one section of two ticks, each with one positioned object.
    head = b"\x00" * 64
    sec = bytes(8) + struct.pack("<II", 1, 2) + bytes(17)
    blocks = b""
    for tick, x in ((1, 1.0), (2, 2.0)):
        data = b"\x60\x73\x85\xfe\xb8\x03" + struct.pack("<3f", x, 5.0, 1.0) + bytes(24)
        pkt = struct.pack("<III", 0xF0190001, 0, len(data)) + data
        payload = struct.pack("<H", 1) + pkt
        blocks += struct.pack("<III", tick, len(payload), 0) + payload
    blocks += struct.pack("<III", 3, 0, 0)
    return head + sec + blocks


def test_synthetic(tmp_path):
    body = _body()
    f = tmp_path / "Match-R01.rec"
    f.write_bytes(_header() + zstandard.ZstdCompressor().compress(body))
    r = rec.read(f)
    assert r.header["version"] == "Y11S1"
    assert r.header_players[0]["playername"] == "alpha"
    assert [s.blocks for s in r.sections] == [3]
    assert [b.tick for b in r.blocks] == [1, 2]
    rd = rnd.read_round(r)
    assert rd.map == "Clubhouse"
    assert [t[1] for t in rd.tracks[0xF0190001]] == [1.0, 2.0]


LOCAL = sorted(glob.glob(os.path.join(os.environ.get("R6_REPLAYS", ""), "**", "*.rec"),
                         recursive=True))


@pytest.mark.local
@pytest.mark.skipif(not LOCAL, reason="no replays on this machine")
def test_local_round():
    rd = rnd.read_round(rec.read(LOCAL[0]))
    assert len(rd.players) == 10
    assert all(any(k == "operator" for k in p.objects.values()) for p in rd.players)
    assert rd.winner in (0, 1)
    assert any(e.kind == "kill" for e in rd.events)
    assert set(rd.roles.values()) == {"attack", "defense"}
