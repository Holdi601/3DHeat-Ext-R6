"""
Rainbow Six Siege's catalogue: what an item id in a replay is (a weapon, a
gadget, an ability, the drone), and what each operator, weapon and gadget is.

Facts, from three places:

- The replay files themselves: every player's items are ids
  (`loadout.py`); which ids an operator carries, across many rounds and
  seasons, says which weapon or gadget an id is - the one the operators
  carrying it have in common (`catalog.json`, `items`: each id with the
  rounds it was seen in and how sure the naming is).
- Ubisoft's operator pages (ubisoft.com/.../game-info/operators/<name>,
  read 2026-11-15): each operator's side, primary and secondary weapons
  with their weapon type, secondary gadgets and unique ability. Loadouts
  change with seasons: the lists are the 2026-11 ones; an id seen with an
  operator who no longer has the item keeps the name the data gives it.
- Roles (`role`, an operator's usual job; a gadget's or ability's role) are
  this project's classification by what the item does, in the community's
  words (hard breacher, intel, trapper, anchor, roamer...), not Ubisoft's.

Not here: weapon damage, fire rate and magazine sizes, operator speed and
health. They change with balance patches and no official text source for
the replays' seasons was at hand, so nothing is guessed. No game assets
(icons, models, textures) are used or shipped; names only.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

#: Weapon classes, the viewer's breakdown words where they fit (`rifle`, `smg`, `shotgun`, `mg`, `pistol`...).
WEAPON_CLASS = {
    "Assault Rifle": "assault rifle", "Submachine Gun": "smg", "Shotgun": "shotgun", "Marksman Rifle": "dmr",
    "Light Machine Gun": "lmg", "Handgun": "handgun", "Machine Pistol": "machine pistol",
    "Hand Cannon": "hand cannon",
}

#: Weapons whose type the operator pages do not state, by what the weapon is.
WEAPON_EXTRA = {
    "Le Roc Shield": "shield", "G52-Tactical Shield": "shield", "Ballistic Shield": "shield",
    "CCE Shield Mk2": "shield", "9X19SVN": "smg", "9x19VSN": "smg", "UZK50Gi": "smg", "Luison": "handgun",
    "Reaper MK2": "machine pistol", "PMR90A2": "assault rifle", "TACIT .45": "handgun", "M249 SAW": "lmg",
}

#: Secondary gadgets: side and role.
GADGETS = {
    "Breach Charge": ("attack", "breach"), "Hard Breach Charge": ("attack", "breach"),
    "Claymore": ("attack", "trap"), "Frag Grenade": ("attack", "utility"),
    "Stun Grenade": ("attack", "utility"), "Smoke Grenade": ("attack", "utility"),
    "Impact EMP Grenade": ("attack", "anti-gadget"),
    "Barbed Wire": ("defense", "denial"), "Deployable Shield": ("defense", "denial"),
    "Bulletproof Camera": ("defense", "intel"), "Observation Blocker": ("defense", "denial"),
    "Impact Grenade": ("defense", "utility"), "Nitro Cell": ("defense", "utility"),
    "Proximity Alarm": ("defense", "intel"),
}

#: Each operator's usual job (community words) and the role of their ability.
ROLES = {
    # attack
    "Sledge": ("soft breacher", "breach"), "Thatcher": ("support", "anti-gadget"), "Ash": ("entry", "breach"),
    "Thermite": ("hard breacher", "breach"), "Twitch": ("support", "anti-gadget"), "Montagne": ("shield", "shield"),
    "Glaz": ("fragger", "utility"), "Fuze": ("flex", "utility"), "Blitz": ("shield", "shield"),
    "IQ": ("intel", "intel"), "Buck": ("soft breacher", "breach"), "Blackbeard": ("fragger", "shield"),
    "Capitão": ("flex", "denial"), "Hibana": ("hard breacher", "breach"), "Jackal": ("intel", "intel"),
    "Ying": ("entry", "utility"), "Zofia": ("soft breacher", "breach"), "Dokkaebi": ("intel", "intel"),
    "Lion": ("intel", "intel"), "Finka": ("support", "support"), "Maverick": ("hard breacher", "breach"),
    "Nomad": ("flank watch", "trap"), "Gridlock": ("flank watch", "denial"), "Nøkk": ("entry", "utility"),
    "Amaru": ("entry", "mobility"), "Kali": ("support", "anti-gadget"), "Iana": ("intel", "intel"),
    "Ace": ("hard breacher", "breach"), "Zero": ("intel", "intel"), "Flores": ("support", "anti-gadget"),
    "Osa": ("support", "shield"), "Sens": ("support", "utility"), "Grim": ("intel", "intel"),
    "Brava": ("support", "anti-gadget"), "Ram": ("soft breacher", "breach"), "Deimos": ("intel", "intel"),
    "Striker": ("flex", "utility"), "Rauora": ("support", "denial"), "Solid Snake": ("intel", "intel"),
    # defense
    "Smoke": ("anchor", "denial"), "Mute": ("anti-gadget", "anti-gadget"), "Castle": ("anchor", "denial"),
    "Pulse": ("intel", "intel"), "Doc": ("anchor", "support"), "Rook": ("anchor", "support"),
    "Kapkan": ("trapper", "trap"), "Tachanka": ("anchor", "denial"), "Jäger": ("anti-gadget", "anti-gadget"),
    "Bandit": ("anti-breach", "anti-breach"), "Frost": ("trapper", "trap"), "Valkyrie": ("intel", "intel"),
    "Caveira": ("roamer", "intel"), "Echo": ("intel", "intel"), "Mira": ("anchor", "intel"),
    "Lesion": ("trapper", "trap"), "Ela": ("roamer", "trap"), "Vigil": ("roamer", "utility"),
    "Maestro": ("anchor", "intel"), "Alibi": ("roamer", "intel"), "Clash": ("anchor", "denial"),
    "Kaid": ("anti-breach", "anti-breach"), "Mozzie": ("anti-gadget", "anti-gadget"),
    "Warden": ("anchor", "utility"), "Goyo": ("anchor", "denial"), "Wamai": ("anti-gadget", "anti-gadget"),
    "Oryx": ("roamer", "mobility"), "Melusi": ("anchor", "denial"), "Aruni": ("anchor", "denial"),
    "Thunderbird": ("support", "support"), "Thorn": ("trapper", "trap"), "Azami": ("anchor", "denial"),
    "Solis": ("intel", "intel"), "Fenrir": ("anchor", "denial"), "Tubarão": ("anti-breach", "anti-breach"),
    "Sentry": ("flex", "utility"), "Skopós": ("intel", "intel"), "Denari": ("trapper", "trap"),
    "Noor": ("anchor", "denial"), "Recruit": ("flex", None),
}

#: Kinds an item is: the slot it fills.
KINDS = ("primary", "secondary", "gadget", "ability", "drone")

_HERE = Path(__file__).resolve().parent


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())


@lru_cache(maxsize=1)
def data() -> dict:
    """`catalog.json`: operators (Ubisoft's loadouts), and item ids named from the replays."""
    return json.loads((_HERE / "catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def operator(name: str | None) -> dict:
    """An operator's entry by name (accents and case ignored), {} when unknown."""
    key = norm(name)
    for n, d in data()["operators"].items():
        if norm(n) == key:
            return {"name": n, **d}
    return {}


def item(item_id: int | None) -> dict:
    """What an item id is: {name, kind, class, role, side, sure}; {} when unknown."""
    if not item_id:
        return {}
    d = data()["items"].get(str(item_id))
    if not d:
        return {}
    return {**d, **describe(d.get("name"), d.get("kind"))}


@lru_cache(maxsize=None)
def describe(name: str | None, kind: str | None) -> dict:
    """A named item's class (weapons) or role (gadgets, abilities), and its side where it has one."""
    if not name:
        return {}
    if kind in ("primary", "secondary"):
        cls = data()["weapons"].get(name, {}).get("class") or WEAPON_EXTRA.get(name)
        return {"class": cls} if cls else {}
    if kind == "gadget" and name in GADGETS:
        side, role = GADGETS[name]
        return {"role": role, "side": side}
    if kind == "ability":
        for op, d in data()["operators"].items():
            if d.get("ability") == name:
                r = _ROLES_N.get(norm(op))
                return {"role": r[1] if r else None, "side": d.get("side"), "operator": op}
    if kind == "drone":
        return {"role": "intel", "side": "attack"}
    return {}


def role_of(operator_name: str | None) -> str | None:
    """An operator's usual job (`ROLES`), None when unknown."""
    r = _ROLES_N.get(norm(operator_name))
    return r[0] if r else None


_ROLES_N = {norm(k): v for k, v in ROLES.items()}
