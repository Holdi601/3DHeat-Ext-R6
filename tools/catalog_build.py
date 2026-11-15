"""
Build `heat3d_ext_r6/catalog.json` from a loadout survey and Ubisoft's operator loadouts.

    python tools/catalog_build.py survey.jsonl loadouts.json heat3d_ext_r6/catalog.json [previous catalog.json]

The survey (`tools/catalog_survey.py`) lists, per round and player, the
operator and the item ids carried, in the file's order. Each player's items
take their slot by that order: an attacker's first non-weapon item that every
attacker carries is the drone; weapons are primary then secondary (a third
weapon is the ability, Capitão's crossbow); of the other items the last is
the secondary gadget and the rest the ability (a shield, Blackbeard's
H.U.L.L.).

An id is named by the operators carrying it in that slot: the name their
loadouts (Ubisoft's operator pages) share. Where several names fit (a weapon
only one operator carries), names already given to other ids are taken out,
and that repeats until nothing changes. What is left ambiguous keeps every
candidate (`candidates`) and `sure: false`. Ids the rules leave open but other
facts settle are named from `RESOLVE`, each with its reason (`by`). With a
previous catalogue, an id it named keeps that name (a bigger survey
names an id differently where loadouts changed between seasons; such
disagreements are listed, not taken).
"""

from __future__ import annotations

import collections
import json
import sys
import unicodedata

CANON = {"capitao": "Capitão", "nokk": "Nøkk", "jager": "Jäger", "tubarao": "Tubarão", "skopos": "Skopós"}
ALIAS = {"9x19svn": "9x19vsn", "m249saw": "m249"}
#: Operators a survey wrote by id (named in game.py since).
OP_ALIAS = {"operator444310693746": "solidsnake"}

#: Ids the slot and headshot rules leave open, named by what else is known (survey of 734 rounds, 2024-2026).
#: Weapon ids are the weapon's asset: a weapon from the game's launch keeps its launch-era id (1366019xxx) for
#: every operator carrying it (UMP45: Castle and Pulse; M870: Bandit and Thorn); a weapon added with an
#: operator gets an id of that season's range (Lion's V308 next to Finka's Spear .308).
RESOLVE: dict[int, tuple[str, str]] = {
    53995319813: ("T-95 LSW", "Flores carries it too"),
    53995319846: ("SIX12", "Ying's other primary is the T-95 LSW"),
    68967567391: ("LMG-E", "Ram carries it too"),
    68967567352: ("M762", "Zofia's other primary is the LMG-E"),
    1366019640: ("UMP45", "headshot share of its kills (64% of 121: not the M1014 shotgun)"),
    1366019520: ("M1014", "Pulse's other primary is the UMP45; 0 headshots in 4 kills"),
    1366019628: ("P90", "headshot share of its kills (73% of 74: not the ITA12L shotgun)"),
    44316587774: ("ITA12L", "Solis's other primary is the P90; 2 headshots in 7 kills"),
    1366019208: ("416-C Carbine", "headshot share (74% of 34: not the M870) and a launch-era id (not the MBZ-19)"),
    1366019556: ("SG-CQB", "a launch-era id; Lion's other primary has an id of his season"),
    55586802030: ("V308", "an id of Lion's season, next to Finka's; 60% headshots"),
    13333481726: ("CAMRS", "Buck's other primary (the C8-SFW has its own id), an id of Buck's season"),
    350658628377: ("Gonne-6", "the one secondary five of its six carriers list"),
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = "".join(ch for ch in s if ch.isalnum())
    return OP_ALIAS.get(s, s)


def main(survey: str, loadouts: str, out: str, previous: str | None = None) -> None:
    rows = [json.loads(line) for line in open(survey, encoding="utf-8")]
    raw = json.load(open(loadouts, encoding="utf-8"))
    ops = {}
    for name, d in raw["operators"].items():
        key = norm(name)
        nice = CANON.get(key, name if not name.isupper() else name.title())
        ops[key] = {"name": nice, "side": d["side"], "primary": [w for w, _ in d["primary"]],
                    "secondary": [w for w, _ in d["secondary"]], "gadgets": list(d["gadgets"]),
                    "ability": d.get("ability"), "types": {w: t for w, t in d["primary"] + d["secondary"]}}
    # The drone: the non-weapon item most attackers carry.
    att = collections.Counter()
    for r in rows:
        for p in r["players"]:
            if ops.get(norm(p["op"]), {}).get("side") == "attack":
                for iid in {i[0] for i in p["items"] if not i[1]}:
                    att[iid] += 1
    drone = att.most_common(1)[0][0] if att else None

    slot_votes = collections.defaultdict(collections.Counter)  # id -> slot -> n
    holders = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # id -> slot -> op -> n
    kills = collections.Counter()
    for r in rows:
        for k in r["kills"]:
            if k.get("w"):
                kills[k["w"]] += 1
        for p in r["players"]:
            op = norm(p["op"])
            weapons = [i[0] for i in p["items"] if i[1]]
            others = [i[0] for i in p["items"] if not i[1] and i[0] != drone]
            slots = {}
            for n, iid in enumerate(weapons):
                slots[iid] = "primary" if n == 0 else "secondary" if n == 1 else "ability"
            for iid in others:
                slots.setdefault(iid, "other")
            if drone in (i[0] for i in p["items"]):
                slots[drone] = "drone"
            for iid, s in slots.items():
                slot_votes[iid][s] += 1
                holders[iid][s][op] += 1

    # A non-weapon item many operators of a side carry is a secondary gadget, one only one carries an ability
    # (Striker and Sentry, who may take any gadget, and Recruit left out of the count).
    anyone = {"striker", "sentry", "recruit"}
    for iid in list(slot_votes):
        if "other" in slot_votes[iid]:
            n_ops = len({o for o in holders[iid]["other"] if o not in anyone})
            slot = "gadget" if n_ops >= 3 else "ability"
            slot_votes[iid][slot] += slot_votes[iid].pop("other")
            for o, c in holders[iid].pop("other").items():
                holders[iid][slot][o] += c

    def candidates(iid):
        slot = slot_votes[iid].most_common(1)[0][0]
        if slot == "drone":
            return slot, {"Drone": 1.0}
        score = collections.Counter()
        names = {}
        total = sum(holders[iid][slot].values())
        for op, c in holders[iid][slot].items():
            d = ops.get(op)
            if not d:
                continue
            lst = {"primary": d["primary"], "secondary": d["secondary"], "gadget": d["gadgets"],
                   "ability": [d["ability"]] if d["ability"] else []}[slot]
            if slot == "ability" and d["ability"] and len(lst) == 1 and holders[iid][slot][op] < c:
                pass
            for nm in set(lst):
                key = ALIAS.get(norm(nm), norm(nm))
                names.setdefault(key, nm)
                score[key] += c
        return slot, {names[k]: s / total for k, s in score.items()} if total else {}

    cands = {iid: candidates(iid) for iid in slot_votes}

    def weapon_type(nm):
        for d in ops.values():
            if nm in d["types"]:
                return d["types"][nm]
        return None
    taken: dict[str, int] = {}
    final: dict[int, tuple[str, list[str]]] = {}
    changed = True
    while changed:
        changed = False
        for iid, (slot, sc) in cands.items():
            if iid in final:
                continue
            best = max(sc.values(), default=0)
            second = max((v for v in sc.values() if v < best), default=0)
            top = [n for n, v in sc.items() if v == best and (v >= 0.8 or (v >= 0.6 and v >= 1.5 * second))
                   and (taken.get(n) in (None, iid) or slot not in ("primary", "secondary"))]
            if len(top) == 1:
                final[iid] = (top[0], [])
                taken[top[0]] = iid
                changed = True
            elif len(top) > 1:
                rest = [n for n in top if n not in taken]
                if len(rest) == 1:
                    final[iid] = (rest[0], [])
                    taken[rest[0]] = iid
                    changed = True
    # A weapon only one operator carries, where one candidate is a shotgun: the headshot share of its kills
    # tells (shotguns well under a third, the rest well over); `likely`, not sure. Ids already named are
    # taken out of the other ids' candidates first.
    hs = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        for k in r["kills"]:
            if k.get("w") and k.get("hs") is not None:
                hs[k["w"]][0] += k["hs"]
                hs[k["w"]][1] += 1
    likely: dict[int, str] = {}
    for _ in range(3):
        for iid, (slot, sc) in cands.items():
            if iid in final or iid in likely or slot not in ("primary", "secondary"):
                continue
            best = max(sc.values(), default=0)
            cand = [nm for nm, v in sc.items() if v == best and nm not in taken and nm not in likely.values()]
            k, n = hs.get(iid, (0, 0))
            if len(cand) == 1 and any(nm in likely.values() for nm, v in sc.items() if v == best):
                likely[iid] = cand[0]
                continue
            if len(cand) != 2 or n < 8:
                continue
            shot = [nm for nm in cand if weapon_type(nm) == "Shotgun"]
            if len(shot) != 1:
                continue
            share = k / n
            if share < 0.3:
                likely[iid] = shot[0]
            elif share > 0.4:
                likely[iid] = next(nm for nm in cand if nm != shot[0])

    items = {}
    for iid, (slot, sc) in cands.items():
        n = sum(slot_votes[iid].values())
        if iid in final:
            name, sure = final[iid][0], True
            cover = round(sc.get(name, 1.0), 2)
            cand = []
        else:
            best = max(sc.values(), default=0)
            cand = sorted(nm for nm, v in sc.items() if v == best and (nm not in taken or slot not in ("primary", "secondary")))
            name, sure, cover = (cand[0] if len(cand) == 1 else likely.get(iid)), False, round(best, 2)
        op_names = sorted({ops[o]["name"] for s in holders[iid] for o in holders[iid][s] if o in ops})
        items[str(iid)] = {"name": name, "kind": slot, "sure": sure, "rounds": n, "kills": kills.get(iid, 0),
                           "fit": cover, "operators": op_names, **({"candidates": cand} if cand else {}),
                           **({"by": "headshot share of its kills"} if iid in likely and not sure else {})}
    # Facts beyond the rules (`RESOLVE`), then what a previous catalogue named for sure.
    for iid, (name, why) in RESOLVE.items():
        v = items.get(str(iid))
        if v and not v["sure"]:
            v.pop("candidates", None)
            v.update({"name": name, "by": why})
    if previous:
        old = json.load(open(previous, encoding="utf-8")).get("items", {})
        for iid, v in items.items():
            o = old.get(iid)
            if not o or not o.get("name") or o["name"] == v.get("name"):
                continue
            # A name the previous catalogue gave stays: where the bigger survey's slot vote disagrees, the
            # disagreement is reported, not taken.
            print(f"  kept {iid} {o['name']!r} (this survey: {v.get('name')!r})", file=sys.stderr)
            v.pop("candidates", None)
            v.pop("by", None)
            v.update({"name": o["name"], "sure": bool(o.get("sure")), "kind": o.get("kind", v["kind"]),
                      **({"by": o["by"]} if o.get("by") else {}),
                      **({"candidates": o["candidates"]} if o.get("candidates") else {})})
    weapons = {}
    for d in ops.values():
        for w, t in d["types"].items():
            if t:
                weapons.setdefault(w, {"type": t})
    from_types = {"Assault Rifle": "assault rifle", "Submachine Gun": "smg", "Shotgun": "shotgun",
                  "Marksman Rifle": "dmr", "Light Machine Gun": "lmg", "Handgun": "handgun",
                  "Machine Pistol": "machine pistol", "Hand Cannon": "hand cannon"}
    for w in weapons.values():
        w["class"] = from_types.get(w["type"])
    doc = {
        "format": "heat3d-r6-catalog", "version": 1,
        "sources": {
            "loadouts": raw.get("source", "ubisoft.com operator pages"),
            "items": f"item ids named from {len(rows)} rounds of official esports replays (2024-2026) by the "
                     "operators carrying them; see tools/catalog_build.py",
        },
        "drone": str(drone) if drone else None,
        "operators": {d["name"]: {k: d[k] for k in ("side", "primary", "secondary", "gadgets", "ability")}
                      for d in sorted(ops.values(), key=lambda x: x["name"])},
        "weapons": dict(sorted(weapons.items())),
        "items": dict(sorted(items.items(), key=lambda x: int(x[0]))),
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    sure = sum(1 for v in items.values() if v["sure"])
    print(f"{len(items)} item ids, {sure} named for sure, drone {drone}", file=sys.stderr)
    for iid, v in sorted(items.items(), key=lambda x: -x[1]["rounds"]):
        if not v["sure"]:
            print("  unsure", iid, v["kind"], v.get("candidates"), v["operators"][:5], v["rounds"], file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:5])
