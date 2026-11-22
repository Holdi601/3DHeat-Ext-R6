"""
What a Match Replay says about its match, without converting it.

    info(path) -> {"map", "map_title", "mode", "date", "duration_s", "players", "teams", "outcome",
                   "game_version", ...}

`path` is one round (`.rec`) or a match folder of them. Only each round's
header strings are read (`rec.py`): the version, the map (`worldid`), the
mode, the teams' names and scores, and the players the header lists. In the
files of Y8S4 on the header is plain before the first compressed frame; in
older files only the start of the compressed stream is unpacked. The round
lengths come from the game clock inside the rounds, which is not read here:
`duration_s` stays None.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import zstandard

from . import game
from .rec import MAGIC, ZSTD, RecError, _header

#: How much of a file is read for its header: the header strings fill a few kilobytes.
HEAD = 1 << 20


def _read_header(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    with open(path, "rb") as f:
        data = f.read(HEAD)
        if data[:7] == MAGIC:
            first = data.find(ZSTD)
            while first < 0 and len(data) < 64 * HEAD:
                more = f.read(HEAD)
                if not more:
                    break
                data += more
                first = data.find(ZSTD)
            if first < 0:
                raise RecError("not a Rainbow Six Siege match replay: no compressed data")
            props, players, _gm, _end = _header(data, first)
            return props, players
        if data[:4] == ZSTD:
            f.seek(0)
            try:
                head = zstandard.ZstdDecompressor().stream_reader(f).read(HEAD)
            except zstandard.ZstdError as e:
                raise RecError(f"not a Rainbow Six Siege match replay: {e}") from None
            if head[:7] != MAGIC:
                raise RecError("not a Rainbow Six Siege match replay")
            props, players, _gm, _end = _header(head, len(head))
            return props, players
    raise RecError("not a Rainbow Six Siege match replay")


def _files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".rec")
        files = files or sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".rec")
        if files:
            return files
        raise RecError("no .rec rounds in this folder")
    raise RecError(f"not found: {path}")


def _int(v: str | None) -> int | None:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _date(stamp: str | None) -> str | None:
    """The header's `datetime` (`YYYY-MM-DD-hh-mm-ss`) as ISO 8601."""
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%d-%H-%M-%S").isoformat()
    except ValueError:
        return None


def info(path: str | Path) -> dict:
    """What the replay says about its match. Raises ValueError for a file that is not an R6 match replay."""
    rounds = []
    for f in _files(Path(path)):
        try:
            rounds.append(_read_header(f))
        except RecError:
            if Path(path).is_file():
                raise
    if not rounds:
        raise RecError("not a Rainbow Six Siege match replay: no round header read")
    rounds.sort(key=lambda r: _int(r[0].get("roundnumber")) or 0)
    first, last = rounds[0][0], rounds[-1][0]

    world = first.get("worldid")
    map_id = game.map_name(world)
    w = _int(world)
    mode = game.MODES.get(_int(first.get("gamemodeid")) or 0)
    match_type = game.MATCH_TYPES.get(_int(first.get("matchtype")) or 0)

    teams = []
    for t in (0, 1):
        name = last.get(f"teamname{t}") or first.get(f"teamname{t}")
        score = _int(last.get(f"teamscore{t}"))
        if name is None and score is None:
            continue
        teams.append({"id": t, "name": name, "score": score})

    # The result by the last round's score, where it decides the match: a team has won more than half
    # of the rounds the match is played over. Otherwise (a round of a match going on, a tie) it is not known here.
    outcome = None
    scores = [t["score"] for t in teams]
    per_match = _int(first.get("roundspermatch"))
    if len(teams) == 2 and None not in scores and per_match and max(scores) * 2 > per_match:
        if scores[0] != scores[1]:
            outcome = {"winner": 0 if scores[0] > scores[1] else 1, "result": "win"}

    # The players as the round headers list them, each once, with the operator of each round.
    players: dict[str, dict] = {}
    for props, listed in rounds:
        for p in listed:
            name = p.get("playername")
            if not name:
                continue
            key = p.get("profileid") or name
            cur = players.setdefault(key, {"name": name, "team": _int(p.get("team")), "profile_id": p.get("profileid"),
                                           "operators": []})
            role = p.get("rolename")
            if role:
                cur["operators"].append(role)

    return {
        "map": map_id,
        "map_title": map_id if w in game.MAPS else None,
        "world_id": world,
        "mode": mode,
        "match_type": match_type,
        "date": _date(first.get("datetime")),
        "duration_s": None,
        "players": list(players.values()),
        "teams": teams,
        "outcome": outcome,
        "game_version": first.get("version"),
        "code_version": _int(first.get("code")),
        "rounds": len(rounds),
        "rounds_per_match": _int(first.get("roundspermatch")),
    }
