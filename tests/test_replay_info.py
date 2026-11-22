"""replay_info on rounds built by hand: the header strings, in both file layouts, one round and a match folder."""

from __future__ import annotations

import pytest
import zstandard

from heat3d_ext_r6 import replay_info


def _s(text: str) -> bytes:
    b = text.encode()
    return bytes([len(b)]) + b"\x00" * 7 + b


def _header(number: int, score0: int, score1: int, operator: str) -> bytes:
    kv = ["playerid", "11", "profileid", "p-11", "playername", "alpha", "team", "0", "rolename", operator,
          "playerid", "12", "profileid", "p-12", "playername", "bravo", "team", "1", "rolename", "SMOKE",
          "version", "Y11S1", "code", "9598646", "datetime", "2026-01-02-03-04-05", "matchtype", "2",
          "worldid", "837214085", "gamemodeid", "327933806", "roundnumber", str(number),
          "teamname0", "Blue", "teamname1", "Orange", "teamscore0", str(score0), "teamscore1", str(score1),
          "roundspermatch", "9"]
    return b"dissect\x00\x02\x00" + _s("UNKNOWN") + b"".join(_s(x) for x in kv)


def _chunked(number: int, score0: int, score1: int, operator: str = "ASH") -> bytes:
    return _header(number, score0, score1, operator) + zstandard.ZstdCompressor().compress(b"\x00" * 256)


def test_one_round(tmp_path):
    f = tmp_path / "Match-R01.rec"
    f.write_bytes(_chunked(0, 1, 0))
    d = replay_info.info(f)
    assert d["map"] == "Clubhouse" and d["map_title"] == "Clubhouse" and d["world_id"] == "837214085"
    assert d["mode"] == "Bomb" and d["match_type"] == "Ranked"
    assert d["date"] == "2026-01-02T03:04:05"
    assert d["duration_s"] is None
    assert d["game_version"] == "Y11S1" and d["code_version"] == 9598646
    assert d["teams"] == [{"id": 0, "name": "Blue", "score": 1}, {"id": 1, "name": "Orange", "score": 0}]
    assert d["outcome"] is None  # one round of a match going on: not decided
    assert d["players"] == [{"name": "alpha", "team": 0, "profile_id": "p-11", "operators": ["ASH"]},
                            {"name": "bravo", "team": 1, "profile_id": "p-12", "operators": ["SMOKE"]}]
    assert d["rounds"] == 1 and d["rounds_per_match"] == 9


def test_match_folder_and_old_layout(tmp_path):
    match = tmp_path / "Match-2026-01-02"
    match.mkdir()
    (match / "Match-R02.rec").write_bytes(_chunked(1, 1, 1, "THATCHER"))
    # Before Y8S4 the whole file is one compressed stream, header included.
    (match / "Match-R01.rec").write_bytes(zstandard.ZstdCompressor().compress(_header(0, 0, 1, "ASH") + bytes(64)))
    (match / "notes.txt").write_text("not a round")
    d = replay_info.info(match)
    assert d["rounds"] == 2
    assert d["teams"][0]["score"] == 1 and d["teams"][1]["score"] == 1
    assert d["outcome"] is None
    assert d["players"][0]["operators"] == ["ASH", "THATCHER"]


def test_decided_match(tmp_path):
    f = tmp_path / "Match-R07.rec"
    f.write_bytes(_chunked(6, 2, 5))
    assert replay_info.info(f)["outcome"] == {"winner": 1, "result": "win"}


def test_unknown_map_keeps_its_number(tmp_path):
    f = tmp_path / "x.rec"
    f.write_bytes(_chunked(0, 0, 0).replace(_s("837214085"), _s("123456789")))
    d = replay_info.info(f)
    assert d["map"] == "map 123456789" and d["map_title"] is None


def test_garbage_is_refused(tmp_path):
    f = tmp_path / "junk.rec"
    f.write_bytes(b"not a replay at all" * 10)
    with pytest.raises(ValueError):
        replay_info.info(f)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        replay_info.info(empty)
