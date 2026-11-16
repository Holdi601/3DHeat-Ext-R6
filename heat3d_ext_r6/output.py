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
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from . import __version__, callouts, catalog, game, impacts, items, sites
from .round import Round

#: Columns from the catalogue on every row of a player (what they play and carry in the round).
GEAR = ("operatorRole", "primary", "primaryClass", "secondary", "secondaryClass", "gadget", "gadgetRole", "ability",
        "abilityRole", "loadout")
#: Columns of a kill or death row: the weapon or gadget the kill was made with.
WEAPON = ("weapon", "weaponClass", "weaponSlot")
#: What a use row is about (`items.py`): the item and its class, how many shots or charges, what was left, and
#: where a thrown or placed gadget came to rest.
USE = ("item", "itemClass")
USE_NUM = ("count", "left", "placedX", "placedY", "placedZ")
#: Who made a mark on the level, as worked out (`impacts.attribute`): player, operator, weapon, weapon class.
BY = ("byPlayer", "byOperator", "byItem", "byItemClass")
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
                  "track", "gadgetType", "other", "otherOperator", "headshot", "won", "matchWon", "roundEndReason", "site", "callout",
                  "teamAlive", "enemyAlive", "state_planted", "surface", "markKind", *BY, *USE, *USE_NUM, "inferred",
                  "detail", "entity"],
    },
}

FLOAT32 = ("x", "y", "z", "yaw", "dirX", "dirY", "dirZ", "roundTime", "clock", "headshot", "won", "matchWon",
           "teamAlive", "enemyAlive", "state_planted", "inferred", *USE_NUM)
INT16 = ("team", "round")
STRINGS = ("match", "player", "track", "teamName", "side", "operator", *GEAR, *WEAPON, "event", "pawn", "gadgetType", "other",
           "otherOperator", "phase", "site", "callout", "roundEndReason", "surface", "markKind", *BY, *USE, "detail")

#: How a kind of object's samples are named in `event`: only the body is the player's position.
EVENT_OF = {"operator": "position", "drone": "drone", "gadget": "gadget"}

NOT_READ = [
    "attachments (sights, barrels, grips): the weapon's record holds small numbers, not named ids",
    "health and damage: not found in the object updates yet",
    "what each placed or thrown gadget object is: not written; a gadget object that appears as its owner uses a "
    "gadget or ability (`items.py`) is named after it (`inferred` 0.9), otherwise `gadgetType` names it from the "
    "owner's loadout and whether it flew (thrown) or stayed (placed), `inferred` the confidence, both names where "
    "that cannot tell",
    "a shot's direction and what it hit: the shots are counted from the ammunition (`shot` rows), not traced",
    "stance (standing, crouching, prone) and leaning: not found in the body's updates",
    "who made a mark on the level: worked out from who faced it as it appeared (`byPlayer`, `inferred` the "
    "confidence); the weapon only where that player's kill in the same moment names it; the size of the opening",
    "who planted or disabled the defuser in Y11 files: the player who stood still through it (`inferred` = 1)",
    "reinforcements: when each was made is read (the team's count of reinforcements left, `reinforce` rows), who "
    "made it is inferred (the defender who stood still through the next seconds; `inferred` = 1 / the number who "
    "did); which wall or hatch, and whether it was later breached, is not read",
    "barricades on doors and windows, walls and floors opened, hatches: a section with level objects, health "
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


#: Secondary gadgets that are thrown (they fly before they land); the rest are placed where the player stands.
THROWN = {"Frag Grenade", "Stun Grenade", "Smoke Grenade", "Impact EMP Grenade", "Impact Grenade", "Nitro Cell"}


def gadget_type(kit: dict[str, str], track: list) -> tuple[str, float]:
    """
    What a gadget object is, from its owner's loadout (secondary gadget and
    ability) and how it moved: one that flew is the thrown one of the two, one
    that stayed is the placed one. (name, confidence); both names joined with
    ` / ` and no confidence where the two cannot be told apart.
    """
    g, a = kit.get("gadget", ""), kit.get("ability", "")
    if not g or not a:
        return (g or a), (0.5 if (g or a) else float("nan"))
    first = track[:40]
    flew = bool(first) and max(math.dist(first[0][1:4], s[1:4]) for s in first) > 1.5
    if g in THROWN:
        return (g, 0.7) if flew else (a, 0.6)
    if flew:
        return a, 0.6
    return f"{g} / {a}", float("nan")


#: A gadget's object appears up to ~4 s before its use is counted (it is in hand, primed or being placed)
#: and up to ~1 s after: ticks.
APPEAR_BEFORE, APPEAR_AFTER = 150, 40


def match_uses(r: Round) -> tuple[dict[int, items.Use], dict[int, int], list[items.Use]]:
    """
    The round's uses (`r.uses`, plus a deploy for each drone as its object
    appears) and which gadget object each one put out: the owner's gadget
    object that appeared nearest in time to the use (`APPEAR_BEFORE`,
    `APPEAR_AFTER`), each object once. Returns (object -> use, id(use) ->
    object, the uses in tick order). A destruction or pick-up of the same
    charge goes with its deploy's object.
    """
    uses = list(r.uses)
    drone_id = int(catalog.data().get("drone") or 0) or None
    by_name = {p.name: p for p in r.players}
    used_by: dict[int, items.Use] = {}
    use_track: dict[int, int] = {}
    for pl in r.players:
        for obj, kind in pl.objects.items():
            track = r.tracks.get(obj)
            if kind == "drone" and track and drone_id:
                u = items.Use("gadget_deploy", track[0][0], pl.name, drone_id, 1, None, None, True)
                uses.append(u)
                used_by[obj], use_track[id(u)] = u, obj
    uses.sort(key=lambda u: (u.tick, u.player, u.kind))
    by_charge: dict[int, int] = {}
    for u in uses:
        if u.charge is not None and u.charge in by_charge and u.kind in ("gadget_destroyed", "gadget_pickup"):
            use_track[id(u)] = by_charge[u.charge]
            continue
        if not u.placed or id(u) in use_track or u.player not in by_name:
            continue
        best = None
        for obj, kind in by_name[u.player].objects.items():
            track = r.tracks.get(obj)
            if kind != "gadget" or not track or obj in used_by:
                continue
            dt = track[0][0] - u.tick
            if -APPEAR_BEFORE <= dt <= APPEAR_AFTER and (best is None or abs(dt) < best[0]):
                best = (abs(dt), obj)
        if best is not None:
            used_by[best[1]], use_track[id(u)] = u, best[1]
            if u.charge is not None:
                by_charge[u.charge] = best[1]
    return used_by, use_track, uses


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
            normal: tuple[float, float, float] | None = None, mark=None, callout: str = "",
            inferred: float = float("nan"), by: tuple[str, str, str, str] | None = None, track: str = "",
            gadget: str = "", use: items.Use | None = None,
            placed: tuple[float, float, float] | None = None) -> None:
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
        cols["callout"].append(callout)
        cols["inferred"].append(inferred)
        cols["track"].append(track or (pl.name if pl is not None and pawn == "operator" else ""))
        cols["gadgetType"].append(gadget)
        for k, v in zip(BY, by or ("", "", "", "")):
            cols[k].append(v)
        iname, idata = label(use.item) if use is not None else ("", {})
        cols["item"].append(iname)
        cols["itemClass"].append(idata.get("class") or idata.get("kind") or "")
        cols["count"].append(float(use.count) if use is not None else float("nan"))
        cols["left"].append(float(use.left) if use is not None and use.left is not None else float("nan"))
        for k, v in zip(("placedX", "placedY", "placedZ"), placed or (float("nan"),) * 3):
            cols[k].append(v)
        cols["detail"].append(detail)
        cols["entity"].append(entity)

    body: dict[str, tuple[int, list]] = {}
    tl = r.callouts
    # Where each callout's room is: the bodies' positions while their callout named it (`sites.py`), and per
    # cell of a metre, the callouts said there (for the marks).
    rooms: dict[str, list[tuple[float, float, float]]] = {}
    cells: dict[tuple[int, int, int], dict[str, int]] = {}
    shooters: list[impacts.Shooter] = []
    drone_name = label(int(catalog.data().get("drone") or 0))[0] or "Drone"
    # Each object its own track: the body is the player's; drones and gadgets are numbered in the order they
    # appear.
    track_name: dict[int, str] = {}
    for pl in r.players:
        count: dict[str, int] = {}
        for obj, kind in sorted(pl.objects.items(), key=lambda kv: (r.tracks.get(kv[0]) or [(1 << 40,)])[0][0]):
            count[kind] = count.get(kind, 0) + 1
            track_name[obj] = pl.name if kind == "operator" else f"{pl.name} {kind} {number}.{count[kind]}"
    try:
        used_by, use_track, uses = match_uses(r)
    except Exception as e:  # noqa: BLE001  (a gadget not matched to its object never costs the round)
        print(f"  round {number}: gadget objects not matched to uses ({type(e).__name__}: {e})", file=sys.stderr)
        used_by, use_track, uses = {}, {}, list(r.uses)
    for pl in r.players:
        for obj, kind in sorted(pl.objects.items(), key=lambda kv: (r.tracks.get(kv[0]) or [(1 << 40,)])[0][0]):
            track = r.tracks.get(obj, [])
            yaw = float("nan")
            line = tl.get(obj)
            heads: list[tuple[int, float, float, float, float]] = []
            # A gadget object is named after the gadget or ability its owner used as it appeared (`match_uses`),
            # else from the loadout and the way it moves (`gadget_type`).
            name = track_name[obj]
            gtype, gconf = ("", float("nan")) if kind == "operator" else \
                (drone_name, 1.0) if kind == "drone" else \
                (label(used_by[obj].item)[0], 0.9) if obj in used_by else \
                gadget_type(kit.get(pl.name, none_kit), track)
            for tick, x, y, z, raw, _flags, _size in track:
                if math.isfinite(raw):
                    yaw = (raw + 90.0 + 180.0) % 360.0 - 180.0
                if kind == "operator" and pl.name in deaths and tick > deaths[pl.name] + 5:
                    break  # the body after death (ragdoll)
                where = line.at(tick) if line else ""
                add(tick, x, y, z, yaw, pl, EVENT_OF[kind], kind, obj, callout=where, track=name, gadget=gtype,
                    inferred=gconf if kind == "gadget" else float("nan"))
                if kind == "operator":
                    heads.append((tick, x, y, z, yaw))
                    if where:
                        rooms.setdefault(where, []).append((x, y, z))
                        c = cells.setdefault((math.floor(x), math.floor(y), math.floor(z / 2.0)), {})
                        c[where] = c.get(where, 0) + 1
            if kind == "operator" and track and (pl.name not in body or len(track) > len(body[pl.name][1])):
                body[pl.name] = (obj, track)
                shooters = [s for s in shooters if s.name != pl.name]
                shooters.append(impacts.Shooter(pl.name, [h[0] for h in heads], heads, deaths.get(pl.name)))

    def callout_of(name: str, tick: int) -> str:
        return callouts.at(tl, body[name][0], tick) if name in body else ""

    def callout_near(x: float, y: float, z: float) -> str:
        """The callout most said within a metre or so of a point (a mark on a wall: either room's)."""
        votes: dict[str, int] = {}
        cx, cy, cz = math.floor(x), math.floor(y), math.floor(z / 2.0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0):
                    for k, n in cells.get((cx + dx, cy + dy, cz + dz), {}).items():
                        votes[k] = votes.get(k, 0) + n * (3 if dx == dy == dz == 0 else 1)
        return max(votes, key=votes.get) if votes else ""

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
                        other=e.other or "", headshot=hs, weapon=e.item, callout=callout_of(e.player, e.tick))
            victim = e.other if e.kind == "kill" else e.player
            if victim in by_name:
                s = at(victim, e.tick)
                if s:  # the death row names what the victim was killed with, as the kill row does
                    add(e.tick, s[1], s[2], s[3], raw_yaw(s), by_name[victim], "death", "operator", body[victim][0],
                        other=e.player if e.kind == "kill" else "", headshot=hs, weapon=e.item,
                        callout=callout_of(victim, e.tick))
        else:
            s = at(e.player, e.tick)
            if s:
                detail = e.text or ""
                if e.of is not None:  # a plant or defuse attempt: the timer as it started and stopped
                    detail = json.dumps({"of": round(e.of, 3), **({"left": round(e.left, 3)} if e.left is not None
                                                                     else {})})
                elif e.kind == "reinforce":  # the team's reinforcements left after this one
                    detail = json.dumps({"left": int(e.text)}) if (e.text or "").isdigit() else ""
                add(e.tick, s[1], s[2], s[3], raw_yaw(s), by_name[e.player], e.kind, "operator", body[e.player][0],
                    detail=detail, callout=callout_of(e.player, e.tick),
                    inferred=e.confidence if e.confidence is not None else
                    (1.0 if e.inferred else 0.0) if e.of is not None else float("nan"))

    # Shots, reloads, ability and gadget uses (`items.py`), each at the user's position; a gadget's object, where
    # one goes with the use, gives where it came to rest (`placedX/Y/Z`, its last sample) and its track's name
    # (`detail` {"object": ...}).
    for u in uses:
        s = at(u.player, u.tick)
        if not s or u.player not in by_name:
            continue
        obj = use_track.get(id(u))
        rest = None
        if obj is not None and r.tracks.get(obj) and by_name[u.player].objects.get(obj) == "gadget":
            # Its last place in the world; an object stuck to another one (a camera on a wall) can end in
            # updates relative to that, near the origin: those are passed over (more than 60 m from the user).
            near = [p for p in r.tracks[obj] if math.dist(p[1:4], s[1:4]) < 60]
            if near:
                rest = (near[-1][1], near[-1][2], near[-1][3])
        add(u.tick, s[1], s[2], s[3], raw_yaw(s), by_name[u.player], u.kind, "operator", body[u.player][0],
            callout=callout_of(u.player, u.tick), use=u, placed=rest,
            detail=json.dumps({"object": track_name[obj]}) if obj in track_name else "")

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
                "operator", body[pl.name][0], detail=detail, callout=callout_of(pl.name, last[0]))

    # Marks on the level (bullet holes and the like), each where it was made (no direction: `impacts.py`);
    # who made it where one player faced it as it appeared, the weapon where their kill then names it.
    marks = impacts.read(r.rec)
    kills_by: dict[str, list[tuple[int, int | None]]] = {}
    for e in r.events:
        if e.kind == "kill" and e.player and e.tick is not None:
            kills_by.setdefault(e.player, []).append((e.tick, e.item))
    near_ticks = 60  # about 1.5 s
    for m, (who, conf) in zip(marks, impacts.attribute(marks, shooters)):
        by = None
        if who:
            item = next((it for t, it in kills_by.get(who, []) if abs(t - m.tick) <= near_ticks and it), None)
            name, d = label(item)
            kind = d.get("kind", "")
            by = (who, op_of.get(who, ""), name, d.get("class") or (kind if kind in ("gadget", "ability") else ""))
        add(m.tick, m.x, m.y, m.z, float("nan"), None, "impact", "mark", m.surface, mark=m,
            callout=callout_near(m.x, m.y, m.z), inferred=conf, by=by)

    owned = {o for p in r.players for o in p.objects}
    ent: dict[str, list] = {c: [] for c in ("round", "tick", "time", "entity", "flags", "bytes", "x", "y", "z")}
    for obj, track in r.tracks.items():
        if obj in owned:
            continue
        for tick, x, y, z, _yaw, flags, nbytes in track:
            ent["round"].append(number), ent["tick"].append(tick), ent["time"].append(offset + (r.seconds(tick) or 0))
            ent["entity"].append(obj), ent["flags"].append(flags), ent["bytes"].append(nbytes)
            ent["x"].append(x), ent["y"].append(y), ent["z"].append(z)
    return cols, ent, rooms


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
            "uses": {k: sum(u.count for u in r.uses if u.player == p.name and u.kind == k)
                     for k in sorted({u.kind for u in r.uses if u.player == p.name})},
        } for p in r.players],
        "events": [{"kind": e.kind, "time_s": round(r.seconds(e.tick) or 0, 2) if e.tick is not None else None,
                    "clock": e.clock, "player": e.player, "other": e.other, "headshot": e.headshot, "text": e.text,
                    **({"item": e.item, "weapon": label(e.item)[0]} if e.item else {}),
                    **({"inferred": e.inferred, "timer_from": e.of, "timer_left": e.left} if e.of is not None else {}),
                    **({"inferred": e.inferred, "confidence": e.confidence} if e.kind == "reinforce" else {})}
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
    rooms: dict[str, list] = {}
    played: list[tuple[str, int, float, float]] = []
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
        cols, ent, seen = _rows(r, number, offset, name, match_won)
        for k, v in seen.items():
            rooms.setdefault(k, []).extend(sites.thin(v, sites.MAX_SAMPLES // 4))
        for k, v in cols.items():
            allc.setdefault(k, []).extend(v)
        for k, v in ent.items():
            alle.setdefault(k, []).extend(v)
        docs.append(_round_doc(r, number, offset))
        end_tick = max((b.tick for b in r.rec.blocks), default=0)
        if r.site:
            played.append((r.site, number, offset, offset + (r.seconds(end_tick) or 0.0)))
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
        "objectives": sites.objectives(h.get("worldid"), played, {k: sites.thin(v) for k, v in rooms.items()}),
        "callouts": sorted(rooms),
        "not_read": NOT_READ,
    }
    (folder / f"{name}.match.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return data
