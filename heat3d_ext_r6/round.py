"""
One round read: the players, where each was tick by tick, the round clock,
the kill feed, the defuser and the result.

Who is who. Each player's block in the snapshot region carries the name, the
operator, a 4-byte id the events use and the 64-bit player id; the pawn table
pairs that player id with the objects the player drives,

    <player id:u64> <1-5 bytes> 0xff <object:u32>

an operator's body (`39 02 <slot> 01 ff` on defence, `21 02 ff` on attack)
and, for attackers in the preparation phase, a drone (`f9 00 <slot> 00 ff`).
Every object whose packets carry a position (flag 0x80 in the fifth byte:
x, y, z as float32 at byte 6, metres, Z up) is followed; the ones the table
names become the players' tracks, the rest are kept as objects.

Time. Blocks are ticks, not seconds: the server ticks at about 29-40 per
second and not evenly. The round clock (`1f 07 ef c9`, seconds, with the
milliseconds left under `22 18 37 46 6c 04`) stands in the event section at
its tick; seconds are put on every tick by following that clock, and where it
jumps up (preparation to action, the end) by the tick rate around the jump.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field

from . import callouts as callout_mod, catalog, game, items, loadout
from .rec import Rec, packets

NAME = b"\x22\x07\x94\x9b\xdc"
OPERATOR = b"\x40\xf2\x15\x04"
DISSECT_ID = b"\x33\xd8\x3d\x4f\x23"
DISSECT_ID_OLD = b"\xe6\xf9\x7d\x86"
PLAYER_ID = b"\xee\xd4\x45\xc8\x08"
SPAWN = b"\xaf\x98\x99\xca"
CLOCK = b"\x1f\x07\xef\xc9"
CLOCK_OLD = b"\x1e\xf1\x11\xab"
CLOCK_MS = b"\x22\x18\x37\x46\x6c\x04"
FEED = b"\x59\x34\xe5\x8b\x04"
KILL = b"\x22\xd9\x13\x3c\xba"
FEED_OLD = b"\x00\x00\x00\x22\xe3\x09\x00\x79"
DEFUSER = b"\x22\xa9\xc8\x58\xd9"
SITE_CURRENT = b"\xfc\xc6\xa8\x60\x01"
WEAPON = b"\xf8\x6c\xdd\x65"  # the kill feed's item: the weapon or gadget the kill was made with
POSITION_FLAG = 0x80


@dataclass
class Player:
    name: str
    team: int
    operator: str | None = None
    operator_id: int | None = None
    event_id: bytes = b""
    player_id: int | None = None
    spawn: str | None = None
    objects: dict[int, str] = field(default_factory=dict)  # object -> "operator" | "drone" | "linked"
    items: list[loadout.Item] = field(default_factory=list)  # carried as the action phase starts
    operator_changes: list[tuple[int | None, int]] = field(default_factory=list)  # (tick, operator id) as set
    item_objects: list[tuple[int, int]] = field(default_factory=list)  # (item object, item id) of every item held


@dataclass
class Event:
    kind: str
    tick: int | None
    clock: float | None
    player: str | None = None
    other: str | None = None
    headshot: bool | None = None
    text: str | None = None
    item: int | None = None  # a kill's weapon or gadget (the kill feed's item id)
    inferred: bool = False  # the player is worked out (who stood still on the site), not written in the file
    left: float | None = None  # a plant or defuse attempt: the defuser's timer when it stopped, seconds
    of: float | None = None  # ... and when it started
    confidence: float | None = None  # for an inferred player: 1 / the number of players who fit


@dataclass
class TimerPacket:
    tick: int
    left: float  # seconds left on the defuser's plant or disable timer
    player: str | None  # where the packet names the player (older seasons)
    clock: float | None


@dataclass
class Round:
    rec: Rec
    number: int
    map: str | None
    mode: str | None
    version: str | None
    players: list[Player]
    tracks: dict[int, list[tuple[int, float, float, float, float, int, int]]]  # object -> (tick, x, y, z, yaw, flags, bytes)
    anchors: list[tuple[int, int, float]]  # tick, phase, seconds left
    events: list[Event]
    site: str | None
    roles: dict[int, str]
    winner: int | None
    win_condition: str | None
    action_tick: int | None
    tick_seconds: list[tuple[int, float]] = field(default_factory=list)
    phase_names: list[str] = field(default_factory=list)
    callouts: dict = field(default_factory=dict)  # track object -> callouts.Timeline (`callouts.py`)
    uses: list = field(default_factory=list)  # shots, reloads, ability and gadget uses (`items.py`)

    def owner(self, obj: int) -> Player | None:
        for p in self.players:
            if obj in p.objects:
                return p
        return None

    def seconds(self, tick: int | None) -> float | None:
        """Seconds since the recording's first tick."""
        if tick is None or not self.tick_seconds:
            return None
        ts = self.tick_seconds
        if tick <= ts[0][0]:
            return max(0.0, ts[0][1] - (ts[0][0] - tick) * _rate(ts, 0))
        if tick >= ts[-1][0]:
            return ts[-1][1] + (tick - ts[-1][0]) * _rate(ts, len(ts) - 2)
        lo, hi = 0, len(ts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ts[mid][0] <= tick:
                lo = mid
            else:
                hi = mid
        (t0, s0), (t1, s1) = ts[lo], ts[hi]
        return s0 + (s1 - s0) * (tick - t0) / (t1 - t0)

    def phase(self, tick: int | None) -> str | None:
        if tick is None or not self.anchors:
            return None
        ph = self.anchors[0][1]
        for t, p, _ in self.anchors:
            if t > tick:
                break
            ph = p
        return self.phase_names[ph] if ph < len(self.phase_names) else f"phase {ph + 1}"


def _rate(ts: list[tuple[int, float]], i: int) -> float:
    i = max(0, min(i, len(ts) - 2))
    if len(ts) < 2:
        return 1 / 30
    dt = ts[i + 1][0] - ts[i][0]
    return (ts[i + 1][1] - ts[i][1]) / dt if dt else 1 / 30


def _fields(b: bytes, p: int, stop: int) -> dict[bytes, bytes]:
    """The tagged fields `22 <field:u32> <len:u8> <value>` from `p` while they continue."""
    out: dict[bytes, bytes] = {}
    stop = min(stop, len(b))
    while p + 6 <= stop and b[p] == 0x22:
        n = b[p + 5]
        out.setdefault(b[p + 1 : p + 5], b[p + 6 : p + 6 + n])
        p += 6 + n
    return out


def _string(b: bytes, p: int) -> tuple[str, int]:
    n = b[p]
    return b[p + 1 : p + 1 + n].decode("utf-8", "replace"), p + 1 + n


def _players(rec: Rec) -> list[Player]:
    body = rec.body
    region_end = rec.snapshot_end or len(body)
    code = rec.code()
    teams = {h.get("playername"): int(h["team"]) for h in rec.header_players if h.get("team", "").isdigit()}
    found: dict[str, Player] = {}
    order: list[str] = []
    starts = [m.start() for m in re.finditer(re.escape(NAME), body[:region_end])]
    for i, p in enumerate(starts):
        try:
            name, q = _string(body, p + 5)
        except IndexError:
            continue
        if not name:
            continue
        stop = starts[i + 1] if i + 1 < len(starts) else min(region_end, p + 8000)
        win = body[q:stop]
        pl = found.get(name)
        if pl is None:
            order.append(name)
            pl = found[name] = Player(name, teams.get(name, 0 if len(order) <= 5 else 1))
        k = win.find(OPERATOR)
        if k >= 0 and k + 22 <= len(win) and win[k + 12] != 0x9D:
            op = struct.unpack_from("<Q", win, k + 14)[0]
            if op and win[k + 22 : k + 23] in (b"\x22", b""):
                pl.operator_id = op
                pl.operator = game.operator_name(op)
        k = win.find(DISSECT_ID if code > game.Y7S2 else DISSECT_ID_OLD)
        if k >= 0 and not pl.event_id:
            pl.event_id = win[k + 5 : k + 9] if code > game.Y7S2 else win[k + 4 : k + 8]
        k = win.find(SPAWN)
        if k >= 0 and pl.spawn is None:
            s, _ = _string(win, k + 4)
            pl.spawn = s.replace("<br/>", ", ") or None
        k = win.find(PLAYER_ID)
        if k >= 0 and pl.player_id is None and k + 13 <= len(win):
            pl.player_id = struct.unpack_from("<Q", win, k + 5)[0]
    # Header ids where the blocks gave none (the header lists the recording team's players).
    for h in rec.header_players:
        pl = found.get(h.get("playername", ""))
        if pl and pl.player_id is None and h.get("playerid", "").isdigit():
            pl.player_id = int(h["playerid"])
    return [found[n] for n in order]


def _link(rec: Rec, players: list[Player], tracks: dict[int, list]) -> None:
    """
    Each object's full update (the one that creates it) carries its owner's
    64-bit player id: the operator's body, drones, thrown and placed gadgets.
    Every object that moves and names a player is that player's; the kind is
    told by its packets' size (a body's update is over 800 bytes, a drone's
    a few hundred and many, a gadget's small).
    """
    body = rec.body
    blocks = [b for b in rec.blocks if b.section == 0]
    starts = [b.start for b in blocks]
    import bisect

    for pl in players:
        if pl.player_id is None:
            continue
        key = struct.pack("<Q", pl.player_id)
        for sec in rec.sections[:1]:
            p = body.find(key, sec.start, sec.end)
            while p != -1:
                i = bisect.bisect_right(starts, p) - 1
                if i >= 0 and p < blocks[i].end:
                    for obj, _aux, q, size in packets(rec, blocks[i]):
                        if q <= p < q + size:
                            if obj in tracks and obj not in pl.objects:
                                big = max(t[6] for t in tracks[obj])
                                pl.objects[obj] = "operator" if big >= 800 else (
                                    "drone" if big >= 150 and len(tracks[obj]) > 100 else "gadget")
                            break
                p = body.find(key, p + 1, sec.end)
    # A player with no body found that way: the pawn table of the snapshot region.
    head = body[: rec.snapshot_end]
    for pl in players:
        if pl.player_id is None or any(k == "operator" for k in pl.objects.values()):
            continue
        key = struct.pack("<Q", pl.player_id)
        p = head.find(key)
        while p != -1:
            e = p + 8
            for j in range(1, 6):
                if head[e + j - 1 : e + j] == b"\xff" and head[e + j + 3 : e + j + 4] == b"\xf0":
                    obj = struct.unpack_from("<I", head, e + j)[0]
                    if obj in tracks and head[e + 1 : e + 2] == b"\x02":
                        pl.objects[obj] = "operator"
                    break
            p = head.find(key, p + 1)


def _tracks(rec: Rec) -> dict[int, list[tuple[int, float, float, float, float, int]]]:
    out: dict[int, list] = {}
    body = rec.body
    unpack = struct.unpack_from
    for blk in rec.blocks:
        if blk.section != 0:
            continue
        for obj, _aux, q, size in packets(rec, blk):
            if size < 18 or body[q + 1 : q + 4] != b"\x73\x85\xfe" or not body[q + 4] & POSITION_FLAG:
                continue
            x, y, z = unpack("<3f", body, q + 6)
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)) or max(abs(x), abs(y), abs(z)) > 5000:
                continue
            if x == 0.0 and y == 0.0:  # an update relative to the object itself (0, 0, height), not a place
                continue
            yaw = float("nan")
            if size >= 38:
                qz, qw = unpack("<2f", body, q + 30)
                a, b = unpack("<2f", body, q + 22)
                if abs(math.hypot(qz, qw) - 1) < 0.02 and abs(a) < 0.05 and abs(b) < 0.05:
                    yaw = math.degrees(2 * math.atan2(qz, qw))
            out.setdefault(obj, []).append((blk.tick, x, y, z, yaw, body[q + 4], size))
    return out


def _anchors(rec: Rec) -> list[tuple[int, int, float]]:
    """(tick, phase, seconds left) at each clock packet; the phase counts the clock's jumps up."""
    body = rec.body
    raw: list[tuple[int, float]] = []
    start = rec.snapshot_end
    if rec.code() >= game.Y8S1:
        p = body.find(CLOCK, start)
        while p != -1:
            t = rec.tick_at(p)
            if t is not None and p + 9 <= len(body):
                sec = struct.unpack_from("<I", body, p + 5)[0]
                k = body.find(CLOCK_MS, p + 9, p + 40)
                left = struct.unpack_from("<I", body, k + 6)[0] / 1000 if k >= 0 else float(sec)
                if sec < 100000 and (k < 0 or abs(left - sec) < 2):
                    raw.append((t, left))
            p = body.find(CLOCK, p + 4)
    raw.sort()
    out: list[tuple[int, int, float]] = []
    phase = 0
    for t, left in raw:
        if out and left > out[-1][2] + 1.5:
            phase += 1
        if out and out[-1][0] == t:
            continue
        out.append((t, phase, left))
    return out


def _tick_seconds(anchors: list[tuple[int, int, float]]) -> list[tuple[int, float]]:
    if len(anchors) < 2:
        return []
    pairs = list(zip(anchors, anchors[1:]))

    def steady(a, b) -> bool:  # the clock running: same phase, about a second a step, a few ticks apart
        return a[1] == b[1] and 0.5 < a[2] - b[2] < 1.5 and b[0] > a[0]

    def rate_near(i: int) -> float:
        near = sorted(((a[2] - b[2]) / (b[0] - a[0]) for a, b in pairs[max(0, i - 8): i + 8] if steady(a, b)))
        if not near:
            near = sorted((a[2] - b[2]) / (b[0] - a[0]) for a, b in pairs if steady(a, b)) or [1 / 30]
        return near[len(near) // 2]

    out = [(anchors[0][0], 0.0)]
    for i, (a, b) in enumerate(pairs):
        if steady(a, b) or (a[1] == b[1] and 0 <= a[2] - b[2] <= 0.5 and b[0] > a[0]):
            out.append((b[0], out[-1][1] + (a[2] - b[2])))
        else:  # a jump (phase change, the clock stopped or set to zero): the ticks at the rate around it
            out.append((b[0], out[-1][1] + (b[0] - a[0]) * rate_near(i)))
    # Shift so the recording's first tick (1) is 0 s.
    first = out[0][1] - (out[0][0] - 1) * _rate(out, 0)
    return [(t, s - first) for t, s in out]


def _feed(rec: Rec, by_event_id: dict[bytes, Player]) -> tuple[list[Event], str | None]:
    body = rec.body
    code = rec.code()
    start = rec.snapshot_end
    events: list[Event] = []
    seen: set[tuple[str, str]] = set()

    # The clock as last seen in stream order, for events outside any block (old files).
    clocks = []
    p = body.find(CLOCK, start)
    while p != -1:
        clocks.append((p, struct.unpack_from("<I", body, p + 5)[0]))
        p = body.find(CLOCK, p + 4)

    def clock_at(off: int) -> float | None:
        c = None
        for o, v in clocks:
            if o > off:
                break
            c = v
        return c

    p = body.find(FEED, start)
    while p != -1:
        q = p + 5
        ok = True
        if code >= game.Y9S1_UPDATE3:
            q += 38
        elif code >= game.Y9S1:
            q += 9
            ok = body[q] == 4
            q += 25
        else:
            k = body.find(FEED_OLD, q + 1, q + 4000)
            ok = k >= 0
            q = k + len(FEED_OLD)
        if ok and q < len(body):
            size = body[q]
            q += 1
            tick = rec.tick_at(p)
            if size == 0 and body[q : q + 5] == KILL:
                fields = _fields(body, q, q + 600)
                killer, q = _string(body, q + 5)
                target, q = _string(body, q + 15)
                item = struct.unpack("<Q", fields[WEAPON])[0] if len(fields.get(WEAPON, b"")) == 8 else None
                if not killer and target:
                    events.append(Event("death", tick, clock_at(p), player=target, item=item or None))
                elif killer and (killer, target) not in seen:
                    seen.add((killer, target))
                    hs = body[q + 56] == 1 if q + 56 < len(body) else None
                    events.append(Event("kill", tick, clock_at(p), player=killer, other=target, headshot=hs,
                                        item=item or None))
            elif size and code < game.Y9S1:
                msg = body[q : q + size].decode("utf-8", "replace")
                kind = "battleye" if "BattlEye" in msg else "leave" if "left" in msg else \
                    "locate" if ("bombs" in msg or "objective" in msg) else "message"
                events.append(Event(kind, tick, clock_at(p), player=msg.split(" ")[0] if kind != "message" else None,
                                    text=msg))
        p = body.find(FEED, p + 5)

    # The defuser's timer while someone plants or disables it: a run of packets counting down.
    timers: list[TimerPacket] = []
    p = body.find(DEFUSER, start)
    while p != -1:
        timer, q = _string(body, p + 5)
        try:
            left = float(timer)
        except ValueError:
            left = None
        tick = rec.tick_at(p)
        if left is not None and tick is not None and math.isfinite(left):
            pl = by_event_id.get(body[q + 34 : q + 38])
            timers.append(TimerPacket(tick, left, pl.name if pl is not None else None, clock_at(p)))
        p = body.find(DEFUSER, p + 5)
    rec._timers = timers  # type: ignore[attr-defined]

    site = None
    p = body.find(SPAWN)
    while p != -1:
        loc, q = _string(body, p + 4)
        if "<br/>" in loc:
            if site is None or body[q + 150 : q + 155] == SITE_CURRENT:
                site = loc.replace("<br/>", ", ")
        p = body.find(SPAWN, p + 4)
    events.sort(key=lambda e: (e.tick if e.tick is not None else 1 << 40))
    return events, site


def read_round(rec: Rec) -> Round:
    h = rec.header
    tracks = _tracks(rec)
    players = _players(rec)
    _link(rec, players, tracks)
    anchors = _anchors(rec)
    events, site = _feed(rec, {p.event_id: p for p in players if p.event_id})
    # The phases by the clock they start with: the action phase starts near 3:00 (the longest),
    # the preparation is the one before it, what follows is after the plant or the round's end.
    first_left: dict[int, float] = {}
    first_tick: dict[int, int] = {}
    for t, p, left in anchors:
        first_left.setdefault(p, left)
        first_tick.setdefault(p, t)
    action = max(first_left, key=lambda p: first_left[p]) if first_left else None
    action_tick = first_tick.get(action) if action is not None else None

    # The operators and items as the action phase starts. The snapshot's are those of the recording's
    # start; a pick in the preparation phase changes them (`loadout.py`).
    picks = loadout.read(rec, action_tick)
    for p in players:
        lo = picks.get(p.name)
        if lo is None:
            continue
        if lo.operator_id:
            p.operator_id = lo.operator_id
            p.operator = game.operator_name(lo.operator_id)
        p.items = lo.items
        p.operator_changes = lo.changes
        p.item_objects = [(it.obj, it.id) for it in lo.held if it.obj]

    # Sides: by the operators each team picked (most of them).
    roles: dict[int, str] = {}
    for team in (0, 1):
        votes = [game.side_of(p.operator) for p in players if p.team == team]
        a, d = votes.count("attack"), votes.count("defense")
        if a != d:
            roles[team] = "attack" if a > d else "defense"
    if len(roles) == 1:
        (t, r), = roles.items()
        roles[1 - t] = "defense" if r == "attack" else "attack"

    # Where everyone is, in callouts; then the plant and defuse attempts, with who made them.
    timelines = callout_mod.read(rec, players, tracks)
    events.extend(_attempts(getattr(rec, "_timers", []), players, tracks, roles, timelines, site, events))
    events.extend(_reinforcements(rec, players, tracks, roles, events))
    events.sort(key=lambda e: (e.tick if e.tick is not None else 1 << 40))
    if any(e.kind == "plant" for e in events) and not roles:
        planter = next(e.player for e in events if e.kind == "plant")
        t = next((p.team for p in players if p.name == planter), None)
        if t is not None:
            roles = {t: "attack", 1 - t: "defense"}

    plant_tick = next((e.tick for e in events if e.kind == "plant" and e.tick is not None), None)
    names = []
    for p in range(max(first_left, default=-1) + 1):
        if p == action:
            names.append("action")
        elif action is not None and p < action:
            names.append("prep")
        elif plant_tick is not None and first_tick.get(p, 0) >= plant_tick - 60:
            names.append("planted")
        else:
            names.append("end")

    winner = None
    try:
        s0, s1 = int(h.get("teamscore0", "")), int(h.get("teamscore1", ""))
        b0, b1 = int(h.get("startingteamscore0", "-1")), int(h.get("startingteamscore1", "-1"))
        if b0 >= 0 and b1 >= 0:
            winner = 0 if s0 > b0 else 1 if s1 > b1 else None
    except ValueError:
        pass
    condition = None
    kinds = [e.kind for e in events]
    team_of = {p.name: p.team for p in players}
    dead = {t: 0 for t in (0, 1)}
    for e in events:
        victim = e.other if e.kind == "kill" else e.player if e.kind == "death" else None
        if victim in team_of:
            dead[team_of[victim]] += 1
    size = {t: sum(1 for p in players if p.team == t) for t in (0, 1)}
    if "defuse" in kinds:
        condition = "defuser disabled"
        w = team_of.get(next(e.player for e in events if e.kind == "defuse"))
        winner = w if winner is None else winner
    elif "plant" in kinds:
        condition = "defuser planted" if winner is None or roles.get(winner) == "attack" else "eliminated after plant"
        if winner is None:
            winner = team_of.get(next(e.player for e in events if e.kind == "plant"))
    elif winner is not None:
        loser = 1 - winner
        condition = "eliminated" if size[loser] and dead[loser] >= size[loser] else \
            "time" if roles.get(winner) == "defense" else "eliminated"
    else:
        for t in (0, 1):
            if size[t] and dead[t] >= size[t]:
                winner, condition = 1 - t, "eliminated"
        if winner is None and roles:
            winner = next(t for t, r in roles.items() if r == "defense")
            condition = "time"

    try:
        number = int(h.get("roundnumber", "0")) + 1
    except ValueError:
        number = 0
    try:
        mode = game.MODES.get(int(h.get("gamemodeid", "0")))
    except ValueError:
        mode = None
    r = Round(rec, number, game.map_name(h.get("worldid")), mode, h.get("version"), players, tracks, anchors,
              events, site, roles, winner, condition, action_tick)
    r.tick_seconds = _tick_seconds(anchors)
    r.phase_names = names
    r.callouts = timelines
    records = {struct.unpack("<Q", o)[0]: n for _p, o, n in loadout._records(rec.body, rec.snapshot_end)}
    r.uses = items.read(rec, loadout._event_section(rec), players, lambda i: catalog.item(i).get("kind"), records)
    return r


#: A plant or a disable takes about 7 s; a timer that starts much higher is something else (the detonation).
ATTEMPT_MAX = 12.0
#: A timer this low has run out: the plant or disable is done.
DONE_AT = 0.15


def _attempts(timers: list[TimerPacket], players: list[Player], tracks: dict, roles: dict[int, str],
              timelines: dict, site: str | None, events: list[Event]) -> list[Event]:
    """
    Plant and defuse attempts from the defuser's timer: each run of packets
    counting down is one attempt; it is done when the timer runs out, else
    interrupted (the player stopped, was stunned or killed, or the round
    ended). Before a plant is done the attempts are plants, after it defuses.
    The packet names the player in the seasons r6-dissect documents; where it
    does not (Y11), the player is the one of the attempting side who stood
    still through the attempt, on the site where the callouts say so (marked
    `inferred`).
    """
    runs: list[list[TimerPacket]] = []
    for tp in sorted(timers, key=lambda x: x.tick):
        cur = runs[-1] if runs else None
        if cur and tp.left <= cur[-1].left + 0.05 and tp.tick - cur[-1].tick <= 60:
            if tp.left < cur[-1].left or tp.player:
                cur.append(tp)
            continue
        runs.append([tp])
    runs = [r for r in runs if r[0].left <= ATTEMPT_MAX and (len(r) >= 2 or r[-1].left <= DONE_AT)]
    deaths: dict[str, int] = {}
    for e in events:
        victim = e.other if e.kind == "kill" else e.player if e.kind == "death" else None
        if victim and e.tick is not None:
            deaths.setdefault(victim, e.tick)
    site_rooms = set(callout_mod.rooms(site))
    out: list[Event] = []
    planted = False
    for run in runs:
        t0, t1 = run[0].tick, run[-1].tick
        kind = "defuse" if planted else "plant"
        who = next((x.player for x in run if x.player), None)
        inferred = False
        if who is None:
            side = "defense" if planted else "attack"
            best = None
            for p in players:
                if roles.get(p.team) != side or (p.name in deaths and deaths[p.name] < t0):
                    continue
                body = next((o for o, k in p.objects.items() if k == "operator" and tracks.get(o)), None)
                if body is None:
                    continue
                span = [s for s in tracks[body] if t0 - 2 <= s[0] <= t1]
                if not span:
                    continue
                x0, y0, z0 = span[0][1:4]
                moved = max(math.dist((x0, y0, z0), s[1:4]) for s in span)
                on_site = callout_mod.at(timelines, body, t0) in site_rooms if site_rooms else False
                if moved > 0.6:
                    continue
                key = (on_site, -moved)
                if best is None or key > best[0]:
                    best = (key, p.name)
            if best is not None:
                who, inferred = best[1], True
        done = run[-1].left <= DONE_AT
        out.append(Event(f"{kind}_start", t0, run[0].clock, player=who, inferred=inferred, of=run[0].left))
        out.append(Event(kind if done else f"{kind}_interrupted", t1, run[-1].clock, player=who, inferred=inferred,
                         left=0.0 if done else run[-1].left, of=run[0].left))
        if done and kind == "plant":
            planted = True
    return out


#: The defending team's reinforcements left (10 a round), on a team object: `23 <object> 0 67 de 20 f8 04 <u32>`.
REINFORCEMENTS = re.compile(rb"\x23(....)\x00\x00\x00\x00\x67\xde\x20\xf8\x04", re.S)
#: Ticks around the count's drop through which the reinforcing player stands still (reinforcing takes seconds).
REINFORCE_BEFORE = 0
REINFORCE_AFTER = 90


def _reinforcements(rec: Rec, players: list[Player], tracks: dict, roles: dict[int, str],
                    events: list[Event]) -> list[Event]:
    """
    A wall or hatch reinforced: the team's count of reinforcements left drops
    by one at that tick. The count is the team's, not a player's, so the
    player is the defender who stood still through the seconds after (marked
    `inferred`, with 1 / the number of defenders who did as the confidence);
    none where no defender did. Worked out here from the files.
    """
    b = rec.body
    series: dict[bytes, list[tuple[int, int]]] = {}
    for m in REINFORCEMENTS.finditer(b, rec.snapshot_end):
        tick = rec.tick_at(m.start())
        if tick is None or m.end() + 4 > len(b):
            continue
        series.setdefault(m.group(1), []).append((tick, struct.unpack_from("<I", b, m.end())[0]))
    deaths: dict[str, int] = {}
    for e in events:
        victim = e.other if e.kind == "kill" else e.player if e.kind == "death" else None
        if victim and e.tick is not None:
            deaths.setdefault(victim, e.tick)
    out: list[Event] = []
    for s in series.values():
        if not s or max(v for _, v in s) > 30:
            continue
        for (_t0, a), (tick, v) in zip(s, s[1:]):
            if v != a - 1:
                continue
            still: list[tuple[float, str]] = []
            for p in players:
                if roles.get(p.team) != "defense" or (p.name in deaths and deaths[p.name] < tick):
                    continue
                body = next((o for o, k in p.objects.items() if k == "operator" and tracks.get(o)), None)
                if body is None:
                    continue
                span = [x for x in tracks[body] if tick - REINFORCE_BEFORE <= x[0] <= tick + REINFORCE_AFTER]
                before = [x for x in tracks[body] if x[0] < tick - REINFORCE_BEFORE]
                if before:
                    span = [before[-1]] + span
                if not span:
                    continue
                moved = max(math.dist(span[0][1:4], x[1:4]) for x in span)
                if moved <= 0.5:
                    still.append((moved, p.name))
            still.sort()
            out.append(Event("reinforce", tick, None, player=still[0][1] if still else None, inferred=bool(still),
                             text=str(v), confidence=round(1 / len(still), 3) if still else None))
    return out