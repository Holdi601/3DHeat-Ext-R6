"""
What a match is written as: one Parquet table (`<match>.parquet`) of every
player's operator, drones and gadgets tick by tick with the round's events
standing on the rows, a match document (`<match>.match.json`) and a sidecar
of every other moving object (`<match>.entities.parquet`), packed into
`<match>.3dheat` (docs/container.md in the viewer).

Siege's world: metres, Z up. The facing is the body's yaw: 0 degrees along
+X, counter-clockwise (worked out against the way players walk).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from . import __version__, catalog, game, impacts
from .round import Round

#: Columns from the catalogue on every row of a player (what they play and carry in the round).
GEAR = ("operatorRole", "primary", "primaryClass", "secondary", "secondaryClass", "gadget", "gadgetRole", "ability",
        "abilityRole", "loadout")
#: Columns of a kill or death row: the weapon or gadget the kill was made with.
WEAPON = ("weapon", "weaponClass", "weaponSlot")
#: Round outcome words (`roundEndReason`) by the reader's win condition.
REASONS = {"eliminated": "elimination", "defuser disabled": "defuser disabled",
           "defuser planted": "defuser detonated", "eliminated after plant": "elimination after plant",
           "time": "time"}

HINTS = {
    "version": 1,
    "kind": "r6-replay",
    "game": "Rainbow Six Siege",
    "axes": {"up": "z", "flipX": False, "flipY": False, "flipZ": False, "scale": 1},
    "entity": {"size": 0.6},
    "columns": {
        "x": "x", "y": "y", "z": "z",
        "time": "time", "timeUnit": "seconds",
        "personId": "player", "teamId": "team", "sessionId": "match",
        "lookMode": "vector", "dirX": "dirX", "dirY": "dirY", "dirZ": "dirZ",
        "extra": ["event", "round", "roundTime", "clock", "phase", "side", "operator", *GEAR, *WEAPON, "pawn",
                  "other", "otherOperator", "headshot", "won", "matchWon", "roundEndReason", "site", "teamAlive",
                  "enemyAlive", "state_planted", "surface", "markKind", "detail", "entity"],
    },
}

FLOAT32 = ("x", "y", "z", "yaw", "dirX", "dirY", "dirZ", "roundTime", "clock", "headshot", "won", "matchWon",
           "teamAlive", "enemyAlive", "state_planted")
INT16 = ("team", "round")
STRINGS = ("match", "player", "teamName", "side", "operator", *GEAR, *WEAPON, "event", "pawn", "other",
           "otherOperator", "phase", "site", "roundEndReason", "surface", "markKind", "detail")

#: How a kind of object's samples are named in `event`: only the body is the player's position.
EVENT_OF = {"operator": "position", "drone": "drone", "gadget": "gadget"}

NOT_READ = [
    "attachments (sights, barrels, grips): the weapon's record holds small numbers, not named ids",
    "health, damage and the shots fired: not found in the object updates yet",
    "what each placed or thrown gadget object is: told apart only by owner and update size (`pawn` = gadget)",
    "who made a mark on the level and with what; the size of the opening a hole makes",
    "walls and floors opened, reinforcements, barricades, hatches: a section with level objects, health "
    "values and positions holds them but is not decoded",
    "camera use and doors: kept whole only as other objects' positions (entities)",
    "online profile ids: read but kept out of the table and this document on purpose",
]


def label(item_id: int | None) -> tuple[str, dict]:
    """An item's name for the table (the candidates joined where the catalogue is not sure) and its entry."""
    if not item_id:
        return "", {}
    d = catalog.item(item_id)
    if not d:
        return f"item {item_id}", {}
    name = d.get("name") or " / ".join(d.get("candidates") or []) or f"item {item_id}"
    return name, d


def gear(pl) -> dict[str, str]:
    """A player's round, from the catalogue: role, weapons and classes, gadget, ability, the loadout list."""
    out = {k: "" for k in GEAR}
    out["operatorRole"] = catalog.role_of(pl.operator) or ""
    weapons = [i for i in pl.items if i.weapon]
    others = [i for i in pl.items if not i.weapon]
    slots: dict[str, int] = {}
    for it in pl.items:
        kind = catalog.item(it.id).get("kind")
        if kind and kind != "drone" and kind not in slots:
            slots[kind] = it.id
    # Where the catalogue does not know an id, its place in the loadout says the slot (`loadout.py`).
    for n, it in enumerate(weapons[:2]):
        slots.setdefault("primary" if n == 0 else "secondary", it.id)
    rest = [i for i in others if catalog.item(i.id).get("kind") != "drone" and str(i.id) != catalog.data().get("drone")]
    if rest:
        slots.setdefault("gadget", rest[-1].id)
        if len(rest) > 1:
            slots.setdefault("ability", rest[0].id)
    for slot in ("primary", "secondary", "gadget", "ability"):
        name, d = label(slots.get(slot))
        out[slot] = name
        if slot in ("primary", "secondary"):
            out[slot + "Class"] = d.get("class") or ""
        else:
            out[slot + "Role"] = d.get("role") or ""
    out["loadout"] = "|".join(out[s] for s in ("primary", "secondary", "gadget", "ability") if out[s])
    return out


def match_name(rounds: list[Round]) -> str:
    r = rounds[0]
    stamp = r.rec.header.get("datetime", "") or "unknown"
    mp = (r.map or "map").replace(" ", "-")
    return f"r6_{mp}_{stamp}"


def _team_names(r: Round) -> dict[int, str]:
    return {t: r.rec.header.get(f"teamname{t}", f"team {t}") for t in (0, 1)}


def _rows(r: Round, number: int, offset: float, match: str,
          match_won: dict[str, float] | None = None) -> tuple[dict[str, list], dict[str, list]]:
    cols: dict[str, list] = {c: [] for c in ("time", *FLOAT32, *INT16, *STRINGS, "entity")}
    side = r.roles
    names = _team_names(r)
    match_won = match_won or {}
    reason = REASONS.get(r.win_condition or "", r.win_condition or "")
    kit = {p.name: gear(p) for p in r.players}
    op_of = {p.name: p.operator or "" for p in r.players}
    none_kit = {k: "" for k in GEAR}
    plant_tick = next((e.tick for e in r.events if e.kind == "plant" and e.tick is not None), None)
    deaths: dict[str, int] = {}
    for e in r.events:
        victim = e.other if e.kind == "kill" else e.player if e.kind == "death" else None
        if victim and e.tick is not None:
            deaths.setdefault(victim, e.tick)
    team_of = {p.name: p.team for p in r.players}
    size = {t: sum(1 for p in r.players if p.team == t) for t in (0, 1)}
    death_ticks = sorted((t, team_of.get(n)) for n, t in deaths.items())

    def alive(team: int, tick: int) -> int:
        return size.get(team, 0) - sum(1 for t, tm in death_ticks if tm == team and t <= tick)

    clock_ticks = [(t, left) for t, _p, left in r.anchors]

    def clock(tick: int) -> float:
        left = float("nan")
        for t, v in clock_ticks:
            if t > tick:
                break
            left = v
        return left

    def add(tick: int, x: float, y: float, z: float, yaw: float, pl, event: str, pawn: str, entity: int,
            other: str = "", headshot: float = float("nan"), detail: str = "", weapon: int | None = None,
            normal: tuple[float, float, float] | None = None, mark=None) -> None:
        sec = r.seconds(tick) or 0.0
        h = math.radians(yaw) if math.isfinite(yaw) else float("nan")
        cols["time"].append(offset + sec)
        cols["x"].append(x), cols["y"].append(y), cols["z"].append(z)
        cols["yaw"].append(yaw)
        if normal is not None:  # a mark: its direction is the surface's normal
            cols["dirX"].append(normal[0]), cols["dirY"].append(normal[1]), cols["dirZ"].append(normal[2])
        else:
            cols["dirX"].append(math.cos(h) if math.isfinite(h) else float("nan"))
            cols["dirY"].append(math.sin(h) if math.isfinite(h) else float("nan"))
            cols["dirZ"].append(0.0 if math.isfinite(h) else float("nan"))
        cols["roundTime"].append(sec)
        cols["clock"].append(clock(tick))
        cols["headshot"].append(headshot)
        team = pl.team if pl is not None else None
        won = float("nan") if r.winner is None or team is None else float(team == r.winner)
        cols["won"].append(won)
        tname = names.get(team, "") if team is not None else ""
        cols["matchWon"].append(match_won.get(tname, float("nan")))
        cols["roundEndReason"].append(reason)
        cols["teamAlive"].append(alive(team, tick) if team is not None else float("nan"))
        cols["enemyAlive"].append(alive(1 - team, tick) if team is not None else float("nan"))
        cols["state_planted"].append(1.0 if plant_tick is not None and tick >= plant_tick else 0.0)
        cols["team"].append(team if team is not None else -1)
        cols["round"].append(number)
        cols["match"].append(match)
        cols["player"].append(pl.name if pl is not None else "")
        cols["teamName"].append(tname)
        cols["side"].append(side.get(team, "") if team is not None else "")
        cols["operator"].append((pl.operator or "") if pl is not None else "")
        g = kit.get(pl.name, none_kit) if pl is not None else none_kit
        for k in GEAR:
            cols[k].append(g[k])
        wname, wd = label(weapon)
        cols["weapon"].append(wname)
        kind = wd.get("kind", "")
        cols["weaponSlot"].append(kind)
        cols["weaponClass"].append(wd.get("class") or (kind if kind in ("gadget", "ability") else ""))
        cols["event"].append(event)
        cols["pawn"].append(pawn)
        cols["other"].append(other)
        cols["otherOperator"].append(op_of.get(other, ""))
        cols["phase"].append(r.phase(tick) or "")
        cols["site"].append(r.site or "")
        cols["surface"].append(str(mark.surface) if mark is not None else "")
        cols["markKind"].append(str(mark.kind) if mark is not None else "")
        cols["detail"].append(detail)
        cols["entity"].append(entity)

    body: dict[str, tuple[int, list]] = {}
    for pl in r.players:
        for obj, kind in pl.objects.items():
            track = r.tracks.get(obj, [])
            yaw = float("nan")
            for tick, x, y, z, raw, _flags, _size in track:
                if math.isfinite(raw):
                    yaw = (raw + 90.0 + 180.0) % 360.0 - 180.0
                if kind == "operator" and pl.name in deaths and tick > deaths[pl.name] + 5:
                    break  # the body after death (ragdoll)
                add(tick, x, y, z, yaw, pl, EVENT_OF[kind], kind, obj)
            if kind == "operator" and track and (pl.name not in body or len(track) > len(body[pl.name][1])):
                body[pl.name] = (obj, track)

    by_name = {p.name: p for p in r.players}

    def at(name: str, tick: int):
        if name not in body:
            return None
        obj, track = body[name]
        best = None
        for s in track:
            if s[0] > tick:
                return best or s
            best = s
        return best

    def raw_yaw(s) -> float:
        return (s[4] + 270.0) % 360.0 - 180.0 if math.isfinite(s[4]) else float("nan")

    for e in r.events:
        if e.tick is None or e.player not in by_name:
            continue
        hs = float("nan") if e.headshot is None else float(e.headshot)
        if e.kind in ("kill", "death"):
            if e.kind == "kill":
                s = at(e.player, e.tick)
                if s:
                    add(e.tick, s[1], s[2], s[3], raw_yaw(s), by_name[e.player], "kill", "operator", body[e.player][0],
                        other=e.other or "", headshot=hs, weapon=e.item)
            victim = e.other if e.kind == "kill" else e.player
            if victim in by_name:
                s = at(victim, e.tick)
                if s:  # the death row names what the victim was killed with, as the kill row does
                    add(e.tick, s[1], s[2], s[3], raw_yaw(s), by_name[victim], "death", "operator", body[victim][0],
                        other=e.player if e.kind == "kill" else "", headshot=hs, weapon=e.item)
        else:
            s = at(e.player, e.tick)
            if s:
                add(e.tick, s[1], s[2], s[3], raw_yaw(s), by_name[e.player], e.kind, "operator", body[e.player][0],
                    detail=e.text or "")

    end_tick = max((b.tick for b in r.rec.blocks), default=0)
    # The round ends at its last kill, defuse or plant's detonation, else when the clock runs out.
    decisive = [e.tick for e in r.events if e.tick is not None and e.kind in ("kill", "death", "defuse")]
    round_end = max(decisive) if decisive and r.win_condition in ("eliminated", "defuser disabled") else end_tick
    detail = json.dumps({"winner": _team_names(r).get(r.winner) if r.winner is not None else None,
                         "winnerSide": side.get(r.winner) if r.winner is not None else None,
                         "reason": r.win_condition, "site": r.site})
    for pl in r.players:
        last = at(pl.name, deaths.get(pl.name, end_tick))  # where they last stood alive
        if last:
            add(round_end, last[1], last[2], last[3], raw_yaw(last), pl, "round_end",
                "operator", body[pl.name][0], detail=detail)

    # Marks on the level (bullet holes and the like), each where it was made, its surface's normal as direction.
    for m in impacts.read(r.rec):
        add(m.tick, m.x, m.y, m.z, float("nan"), None, "impact", "mark", m.surface, normal=(m.nx, m.ny, m.nz),
            mark=m)

    owned = {o for p in r.players for o in p.objects}
    ent: dict[str, list] = {c: [] for c in ("round", "tick", "time", "entity", "flags", "bytes", "x", "y", "z")}
    for obj, track in r.tracks.items():
        if obj in owned:
            continue
        for tick, x, y, z, _yaw, flags, nbytes in track:
            ent["round"].append(number), ent["tick"].append(tick), ent["time"].append(offset + (r.seconds(tick) or 0))
            ent["entity"].append(obj), ent["flags"].append(flags), ent["bytes"].append(nbytes)
            ent["x"].append(x), ent["y"].append(y), ent["z"].append(z)
    return cols, ent


def table(cols: dict[str, list]) -> pa.Table:
    order = np.argsort(np.asarray(cols["time"], dtype=np.float64), kind="stable")
    arrays = [pa.array(np.asarray(cols["time"], dtype=np.float64)[order])]
    fields = [pa.field("time", pa.float64())]
    for c in FLOAT32:
        arrays.append(pa.array(np.asarray(cols[c], dtype=np.float32)[order]))
        fields.append(pa.field(c, pa.float32()))
    for c in INT16:
        arrays.append(pa.array(np.asarray(cols[c], dtype=np.int16)[order]))
        fields.append(pa.field(c, pa.int16()))
    arrays.append(pa.array(np.asarray(cols["entity"], dtype=np.int64)[order]))
    fields.append(pa.field("entity", pa.int64()))
    for c in STRINGS:
        vals = cols[c]
        arrays.append(pa.array([vals[i] for i in order], type=pa.string()).dictionary_encode())
        fields.append(pa.field(c, pa.dictionary(pa.int32(), pa.string())))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields, metadata={"heat3d": json.dumps(HINTS)}))


def _round_doc(r: Round, number: int, offset: float) -> dict[str, Any]:
    names = _team_names(r)
    h = r.rec.header
    end_tick = max((b.tick for b in r.rec.blocks), default=0)
    return {
        "round": number,
        "file": r.rec.path.name,
        "starts_at": round(offset, 3),
        "duration_s": round(r.seconds(end_tick) or 0.0, 3),
        "ticks": end_tick,
        "site": r.site,
        "sides": {names[t]: s for t, s in r.roles.items()},
        "winner": names.get(r.winner) if r.winner is not None else None,
        "winner_side": r.roles.get(r.winner) if r.winner is not None else None,
        "win_condition": r.win_condition,
        "round_end_reason": REASONS.get(r.win_condition or "", r.win_condition),
        "score_after": {names[0]: h.get("teamscore0"), names[1]: h.get("teamscore1")},
        "phases": [{"phase": r.phase_names[p] if p < len(r.phase_names) else p, "from_s": round(r.seconds(t) or 0, 2),
                    "clock_s": round(left, 2)}
                   for i, (t, p, left) in enumerate(r.anchors) if i == 0 or r.anchors[i - 1][1] != p],
        "players": [{
            "name": p.name, "team": names.get(p.team), "side": r.roles.get(p.team), "operator": p.operator,
            "operator_id": p.operator_id, "spawn": p.spawn,
            "operator_picks": [{"tick": t, "operator": game.operator_name(o)} for t, o in p.operator_changes],
            "items": [{"id": it.id, "name": label(it.id)[0], "kind": catalog.item(it.id).get("kind"),
                       "sure": catalog.item(it.id).get("sure"), "weapon_slot": it.weapon} for it in p.items],
            "objects": {k: sum(1 for v in p.objects.values() if v == k) for k in ("operator", "drone", "gadget")},
            "samples": sum(len(r.tracks.get(o, [])) for o, k in p.objects.items() if k == "operator"),
        } for p in r.players],
        "events": [{"kind": e.kind, "time_s": round(r.seconds(e.tick) or 0, 2) if e.tick is not None else None,
                    "clock": e.clock, "player": e.player, "other": e.other, "headshot": e.headshot, "text": e.text,
                    **({"item": e.item, "weapon": label(e.item)[0]} if e.item else {})}
                   for e in r.events],
        "objects_moving": len(r.tracks),
        "sections": [{"id": s.id, "blocks": s.blocks, "ticks": [s.first_tick, s.last_tick], "bytes": s.end - s.start}
                     for s in r.rec.sections],
    }


def write(rounds: list[Round], folder: str | Path) -> Path:
    """`<match>.parquet`, `<match>.match.json`, `<match>.entities.parquet` in `folder`."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rounds = sorted(rounds, key=lambda r: r.number)
    name = match_name(rounds)
    allc: dict[str, list] = {}
    alle: dict[str, list] = {}
    offset = 0.0
    docs = []
    # The match's result by team name: the final score (the last round's header), 1 won, 0 lost, 0.5 drawn.
    last = rounds[-1].rec.header
    try:
        s0, s1 = int(last.get("teamscore0", "")), int(last.get("teamscore1", ""))
        n0, n1 = _team_names(rounds[-1])[0], _team_names(rounds[-1])[1]
        match_won = {n0: 1.0 if s0 > s1 else 0.0 if s0 < s1 else 0.5, n1: 1.0 if s1 > s0 else 0.0 if s1 < s0 else 0.5}
    except ValueError:
        match_won = {}
    for i, r in enumerate(rounds):
        number = r.number or i + 1
        cols, ent = _rows(r, number, offset, name, match_won)
        for k, v in cols.items():
            allc.setdefault(k, []).extend(v)
        for k, v in ent.items():
            alle.setdefault(k, []).extend(v)
        docs.append(_round_doc(r, number, offset))
        end_tick = max((b.tick for b in r.rec.blocks), default=0)
        offset += (r.seconds(end_tick) or 0.0) + 5.0
    data = folder / f"{name}.parquet"
    pq.write_table(table(allc), data, compression="snappy", row_group_size=256_000)  # the viewer reads snappy
    if alle.get("tick"):
        ent_t = pa.table({
            "round": pa.array(np.asarray(alle["round"], dtype=np.int16)),
            "tick": pa.array(np.asarray(alle["tick"], dtype=np.int32)),
            "time": pa.array(np.asarray(alle["time"], dtype=np.float64)),
            "entity": pa.array(np.asarray(alle["entity"], dtype=np.int64)),
            "flags": pa.array(np.asarray(alle["flags"], dtype=np.uint8)),
            "bytes": pa.array(np.asarray(alle["bytes"], dtype=np.int32)),
            "x": pa.array(np.asarray(alle["x"], dtype=np.float32)),
            "y": pa.array(np.asarray(alle["y"], dtype=np.float32)),
            "z": pa.array(np.asarray(alle["z"], dtype=np.float32)),
        }).replace_schema_metadata({"heat3d": json.dumps({"kind": "r6-replay-entities", "match": name})})
        pq.write_table(ent_t, folder / f"{name}.entities.parquet", compression="zstd", row_group_size=256_000)
    first = rounds[0]
    h = first.rec.header
    names = _team_names(first)
    try:
        mtype = game.MATCH_TYPES.get(int(h.get("matchtype", "0")))
    except ValueError:
        mtype = None
    doc = {
        "format": "heat3d-r6-replay-match",
        "version": 1,
        "tool": "heat3d-r6-replay",
        "tool_version": __version__,
        "match": name,
        "game": "Rainbow Six Siege",
        "map": first.map,
        "world_id": h.get("worldid"),
        "mode": first.mode,
        "match_type": mtype,
        "game_version": h.get("version"),
        "code_version": first.rec.code(),
        "recorded": h.get("datetime"),
        "spectator_recording": h.get("isspectator") == "1",
        "teams": [names[0], names[1]],
        "final_score": {names[0]: rounds[-1].rec.header.get("teamscore0"),
                        names[1]: rounds[-1].rec.header.get("teamscore1")},
        "rounds_per_match": h.get("roundspermatch"),
        "rounds": docs,
        "rows": len(allc.get("time", [])),
        "units": "metres; Z up; yaw degrees from +X counter-clockwise",
        "time": "seconds from the first round's first tick; rounds follow each other with 5 s between; "
                "roundTime from the round's first tick; clock is the round clock left (prep, then action)",
        "not_read": NOT_READ,
    }
    (folder / f"{name}.match.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return data
