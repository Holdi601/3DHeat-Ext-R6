# Changelog

## 0.2.0

- Operators as picked: the operator and loadout each player has as the action phase starts, followed through the preparation phase (`loadout.py`). Before, an attacker who picked again in the preparation phase kept the operator of the recording's start.
- The catalogue (`catalog.json`, `catalog.py`): 199 item ids named from the replays (weapons, secondary gadgets, abilities, the drone), each operator's loadout (Ubisoft's operator pages), weapon classes, operator, gadget and ability roles; `tools/catalog_survey.py` and `tools/catalog_build.py` rebuild it.
- Columns: `operatorRole`, `primary`, `primaryClass`, `secondary`, `secondaryClass`, `gadget`, `gadgetRole`, `ability`, `abilityRole`, `loadout` on every row of a player; `weapon`, `weaponClass`, `weaponSlot`, `otherOperator` on kill and death rows (the kill feed's item id); `roundEndReason` and `matchWon` on every row.
- Marks on the level (`impacts.py`): bullet holes and the like as `impact` rows with their exact position, the surface's normal, the level object (`surface`) and the mark's kind (`markKind`).
- Solid Snake's operator id; Rauora and Solid Snake counted as attackers.

## 0.1.0

- First reader: header, players, operators, positions of bodies, drones and gadgets, kill feed, defuser, round clock, site, result; `.3dheat` output.