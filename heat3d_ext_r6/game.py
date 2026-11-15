"""
Rainbow Six Siege's identifiers: maps (`worldid`), operators, game modes and
match types. Facts of the game, gathered from the values r6-dissect
(github.com/redraskal/r6-dissect, MIT) lists; a value not listed is kept as
its number. Several maps have more than one id (reworks).
"""

MAPS = {
    837214085: "Clubhouse",
    1378191338: "Kafe Dostoyevsky",
    1460220617: "Kanal",
    1767965020: "Yacht",
    2609218856: "Presidential Plane",
    2609221242: "Consulate",
    2697268122: "Bartlett University",
    42090092951: "Coastline",
    53627213396: "Tower",
    88107330328: "Villa",
    126196841359: "Fortress",
    127951053400: "Hereford Base",
    199824623654: "Theme Park",
    231702797556: "Oregon",
    237873412352: "House",
    259816839773: "Chalet",
    276279025182: "Skyscraper",
    305979357167: "Border",
    329867321446: "Favela",
    355496559878: "Bank",
    362605108559: "Outback",
    365284490964: "Emerald Plains",
    270063334510: "Stadium Bravo",
    378595635123: "Nighthaven Labs",
    379218689149: "Consulate",
    388073319671: "Lair",
    405306299908: "Stadium 2020",
    413779563590: "Bank",
    407987100456: "Border",
    407558616688: "Chalet",
    407193663917: "Clubhouse",
    413845419788: "Kafe Dostoyevsky",
    417890697769: "Lair",
    418119057546: "Nighthaven Labs",
    418126004176: "Consulate",
    # Named by their site callouts (Commander's Office and Dormitory; Aviator Room and Statuary Room).
    398899676157: "Fortress",
    409325881472: "Villa",
}

OPERATORS = {
    359656345734: "Recruit",
    92270642682: "Castle",
    104189664704: "Aruni",
    161289666230: "Kaid",
    174977508820: "Mozzie",
    92270642708: "Pulse",
    104189664390: "Ace",
    92270642214: "Echo",
    378305069945: "Azami",
    391752120891: "Solis",
    92270644215: "Capitão",
    92270644189: "Zofia",
    92270644267: "Dokkaebi",
    104189662920: "Warden",
    92270644319: "Mira",
    92270642344: "Sledge",
    104189664273: "Melusi",
    92270642526: "Bandit",
    92270642188: "Valkyrie",
    92270644059: "Rook",
    92270641980: "Kapkan",
    291191151607: "Zero",
    104189664038: "Iana",
    92270642656: "Ash",
    92270642136: "Blackbeard",
    288200867444: "Osa",
    373711624351: "Thorn",
    92270642604: "Jäger",
    104189663920: "Kali",
    92270642760: "Thermite",
    288200866821: "Brava",
    104189663607: "Amaru",
    92270642292: "Ying",
    92270642266: "Lesion",
    92270644007: "Doc",
    104189661861: "Lion",
    92270642032: "Fuze",
    92270642396: "Smoke",
    92270644293: "Vigil",
    92270642318: "Mute",
    104189663698: "Goyo",
    104189663803: "Wamai",
    92270644163: "Ela",
    92270644033: "Montagne",
    104189663024: "Nøkk",
    104189662071: "Alibi",
    104189661965: "Finka",
    92270644241: "Caveira",
    161289666248: "Nomad",
    288200867351: "Thunderbird",
    384797789346: "Sens",
    92270642578: "IQ",
    92270642539: "Blitz",
    92270642240: "Hibana",
    104189662384: "Maverick",
    328397386974: "Flores",
    92270642474: "Buck",
    92270644111: "Twitch",
    174977508808: "Gridlock",
    92270642422: "Thatcher",
    92270642084: "Glaz",
    92270644345: "Jackal",
    374667788042: "Grim",
    291437347686: "Tachanka",
    104189664155: "Oryx",
    92270642500: "Frost",
    104189662175: "Maestro",
    104189662280: "Clash",
    288200867339: "Fenrir",
    395943091136: "Ram",
    288200867549: "Tubarão",
    374667787816: "Deimos",
    409899350463: "Striker",
    409899350403: "Sentry",
    386098331713: "Skopos",
    386098331923: "Rauora",
    374667787937: "Denari",
    444310693746: "Solid Snake",  # named by its loadout (F2, PMR90A2, its own secondary and ability), Y11
}

MODES = {
    327933806: "Bomb",
    1983085217: "Secure Area",
    2838806006: "Hostage",
    400168582901: "Quick Match Bomb",
}

MATCH_TYPES = {
    1: "Quick Match",
    2: "Ranked",
    3: "Custom Game Local",
    4: "Custom Game Online",
    8: "Standard",
    9: "Unranked",
}


#: Code versions (the header's `code`) where the event layouts change.
Y7S2 = 7040830
Y7S4 = 7338571
Y8S1 = 7408213
Y8S2 = 7601998
Y8S4 = 7921866
Y9S1 = 8111697
Y9S1_UPDATE3 = 8211379
Y9S3 = 8506016
Y9S4 = 8673114


def map_name(world: int | str | None) -> str | None:
    try:
        w = int(world)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return MAPS.get(w, f"map {w}")


def operator_name(op: int | None) -> str | None:
    if not op:
        return None
    return OPERATORS.get(op, f"operator {op}")


#: The attacking operators; every other named operator defends (Recruit can do either).
ATTACKERS = {
    "Sledge", "Thatcher", "Ash", "Thermite", "Twitch", "Montagne", "Glaz", "Fuze", "Blitz", "IQ", "Buck",
    "Blackbeard", "Capitão", "Hibana", "Jackal", "Ying", "Zofia", "Dokkaebi", "Lion", "Finka", "Maverick",
    "Nomad", "Gridlock", "Nøkk", "Amaru", "Kali", "Iana", "Ace", "Zero", "Flores", "Osa", "Sens", "Grim",
    "Brava", "Ram", "Deimos", "Striker", "Rauora", "Solid Snake",
}


def side_of(operator: str | None) -> str | None:
    if not operator or operator == "Recruit" or operator.startswith("operator "):
        return None
    return "attack" if operator in ATTACKERS else "defense"
