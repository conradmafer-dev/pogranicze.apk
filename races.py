"""Alien Colonies playable factions: independent authoritative balance catalog.

Tuple layouts match the legacy roles. Internal role keys deliberately stay stable;
every faction supplies its own names, art, costs, construction times and ship stats.
"""
from __future__ import annotations

NEUTRAL_RULES = {
    "production_multipliers": {"metal": 1.0, "crystal": 1.0, "fuel": 1.0},
    "energy_supply_per_level": 100,
    "energy_use_per_level": {"metal_mine": 20, "crystal_mine": 25, "refinery": 25},
    "first_volley_multiplier": 1.0, "regeneration_fraction": 0.0,
    "damage_reduction": 0.0,
}

RACES = {
    "zetans": {
        "name": "Zetanie",
        "description": "Zieloni odkrywcy sterujący grawitacją i szmaragdową plazmą. Gładkie kopuły i srebrne dyski tworzą ich kolonie.",
        "trait": "Pierwsza salwa +35% obrażeń. Produkcja kryształów +25%. Szybkie, lekkie dyski.",
        "tradeoff": "Produkcja metalu −10%. Kopalnie zużywają więcej energii. Lżejsze kadłuby.",
        "weapon_name": "Plazma fazowa",
        "rules": {
            "production_multipliers": {"metal": 0.9, "crystal": 1.25, "fuel": 1.0},
            "energy_supply_per_level": 100,
            "energy_use_per_level": {"metal_mine": 23, "crystal_mine": 29, "refinery": 29},
            "first_volley_multiplier": 1.35, "regeneration_fraction": 0.0,
            "damage_reduction": 0.0,
        },
        "buildings": {
            "metal_mine": ("Ekstraktor grawitacyjny", "Podnosi rudy z głębin polem grawitacyjnym. Produkcja metalu rasy: −10%.", (180, 90, 0), 105),
            "crystal_mine": ("Rezonator kryształów", "Skupia kryształy w lewitujących pierścieniach. Produkcja kryształów rasy: +25%.", (135, 140, 0), 130),
            "refinery": ("Destylator jonowy", "Oddziela paliwo w srebrnych komorach jonowych.", (195, 165, 0), 155),
            "power_plant": ("Rdzeń osobliwości", "Zapewnia 100 energii na poziom. Ekstraktor pobiera 23, rezonator i destylator po 29 na poziom.", (165, 105, 0), 110),
            "shipyard": ("Dok antygrawitacyjny", "Montuje dyski i okręty fazowe. Poziom 2 odblokowuje Archonta.", (360, 290, 70), 215),
            "lab": ("Obserwatorium psioniczne", "Bada napęd grawitacyjny i plazmę fazową.", (315, 355, 70), 205),
        },
        "research": {
            "propulsion": ("Napęd grawitacyjny", "Każdy poziom przyspiesza podróże o 15% względem bazowej prędkości okrętu.", (300, 480, 175), 205),
            "weapons": ("Plazma fazowa", "Atak +15% na poziom. Pierwsza salwa Zetan mnoży końcowy atak przez 1,35.", (440, 380, 135), 220),
        },
        "ships": {
            # name, description, cost, seconds, attack, hull, hold, fuel, speed
            "scout": ("Oko Zety", "Lekki dysk zwiadowczy z napędem grawitacyjnym.", (85, 125, 25), 50, 3, 12, 10, 1, 2.3),
            "cargo": ("Arka lewitacyjna", "Szybki transport w pierścieniu antygrawitacyjnym.", (220, 195, 50), 105, 4, 40, 1300, 2, 1.3),
            "colonizer": ("Siewca światów", "Rozkłada srebrne kopuły nowej kolonii.", (1450, 1250, 350), 365, 3, 72, 550, 7, 1.05),
            "frigate": ("Promień", "Lekki okręt z plazmą fazową; pierwsza salwa jest o 35% silniejsza.", (305, 230, 70), 130, 32, 76, 70, 3, 1.6),
            "cruiser": ("Archont", "Srebrny okręt dowodzenia z pierścieniem plazmowym.", (1050, 940, 220), 310, 100, 250, 190, 8, 1.1),
        },
    },
    "symbionts": {
        "name": "Symbionci",
        "description": "Organiczna cywilizacja hodująca żywe kolonie i okręty. Fioletowe koralowce otaczają bursztynowe organy.",
        "trait": "Po każdej rundzie leczy 35% ran ocalałych kadłubów. Produkcja paliwa +20%.",
        "tradeoff": "Produkcja kryształów −15%. Okręty rosną dłużej i podróżują wolniej.",
        "weapon_name": "Zarodniki bojowe",
        "rules": {
            "production_multipliers": {"metal": 1.0, "crystal": 0.85, "fuel": 1.2},
            "energy_supply_per_level": 85,
            "energy_use_per_level": {"metal_mine": 17, "crystal_mine": 21, "refinery": 21},
            "first_volley_multiplier": 1.0, "regeneration_fraction": 0.35,
            "damage_reduction": 0.0,
        },
        "buildings": {
            "metal_mine": ("Korzenie żelazne", "Żywe korzenie rozpuszczają skały i zbierają metal.", (175, 60, 20), 145),
            "crystal_mine": ("Ogród krzemowy", "Hoduje kryształy w fioletowych pąkach. Produkcja kryształów rasy: −15%.", (130, 95, 25), 175),
            "refinery": ("Gruczoł paliwowy", "Fermentuje paliwo w bursztynowych pęcherzach. Produkcja paliwa rasy: +20%.", (190, 110, 20), 200),
            "power_plant": ("Serce kolonii", "Daje 85 energii na poziom. Korzenie zużywają 17, ogród i gruczoł po 21 energii na poziom.", (155, 65, 20), 140),
            "shipyard": ("Gniazdo rojowe", "Hoduje żywe okręty. Poziom 2 pozwala wyhodować Lewiatana.", (340, 190, 100), 280),
            "lab": ("Splot pamięci", "Żywa sieć bada ewolucję żagli i zarodników bojowych.", (300, 235, 100), 285),
        },
        "research": {
            "propulsion": ("Żagle próżniowe", "Każdy poziom przyspiesza podróże o 15% względem bazowej prędkości organizmu.", (295, 335, 245), 285),
            "weapons": ("Zarodniki bojowe", "Atak +15% na poziom. Żywe kadłuby po rundzie leczą 35% ran ocalałych jednostek; zniszczone nie odrastają.", (425, 255, 185), 280),
        },
        "ships": {
            "scout": ("Świetlik", "Żywy zwiadowca z czułkami odbierającymi echo gwiazd.", (85, 80, 40), 75, 2, 19, 15, 1, 1.55),
            "cargo": ("Wieloryb próżniowy", "Przewozi zapasy w pojemnych żywych komorach.", (210, 125, 75), 145, 3, 65, 1800, 2, 0.85),
            "colonizer": ("Matka kolonii", "Przenosi zarodek serca kolonii i zasiewa nowy świat.", (1360, 850, 500), 500, 2, 115, 750, 6, 0.65),
            "frigate": ("Żądło", "Organiczny łowca wyrzucający chmury zarodników.", (300, 150, 100), 180, 25, 120, 100, 2, 1.0),
            "cruiser": ("Lewiatan", "Ogromny żywy okręt z regenerującym się pancerzem.", (1020, 635, 310), 435, 80, 410, 280, 7, 0.7),
        },
    },
    "automatons": {
        "name": "Automatony",
        "description": "Autonomiczne maszyny wznoszące grafitowe fortece i miedziane linie produkcyjne. Ich broń przyspiesza metal do prędkości orbitalnych.",
        "trait": "Pancerz zmniejsza każde otrzymane obrażenia o 12%. Produkcja metalu +25%.",
        "tradeoff": "Produkcja paliwa −20%. Ciężkie okręty są wolniejsze i zużywają więcej paliwa.",
        "weapon_name": "Akceleratory kinetyczne",
        "rules": {
            "production_multipliers": {"metal": 1.25, "crystal": 1.0, "fuel": 0.8},
            "energy_supply_per_level": 120,
            "energy_use_per_level": {"metal_mine": 25, "crystal_mine": 31, "refinery": 31},
            "first_volley_multiplier": 1.0, "regeneration_fraction": 0.0,
            "damage_reduction": 0.12,
        },
        "buildings": {
            "metal_mine": ("Kombinat wiertniczy", "Wydobywa rudę za pomocą ciężkich autonomicznych wierteł. Produkcja metalu rasy: +25%.", (245, 65, 0), 95),
            "crystal_mine": ("Separator krzemowy", "Przemysłowo oddziela kryształy od urobku.", (185, 100, 0), 120),
            "refinery": ("Kraker syntetyczny", "Produkuje paliwo do ciężkich silników. Produkcja paliwa rasy: −20%.", (270, 120, 0), 145),
            "power_plant": ("Reaktor przemysłowy", "Daje 120 energii na poziom. Kombinat pobiera 25, separator i kraker po 31 na poziom.", (220, 75, 0), 95),
            "shipyard": ("Kuźnia orbitalna", "Składa ciężkie maszyny bojowe. Poziom 2 odblokowuje Bastion.", (490, 210, 95), 190),
            "lab": ("Rdzeń obliczeniowy", "Projektuje silniki impulsowe i akceleratory kinetyczne.", (430, 255, 95), 190),
        },
        "research": {
            "propulsion": ("Silniki impulsowe", "Każdy poziom przyspiesza podróże o 15% względem bazowej prędkości maszyny.", (430, 365, 235), 190),
            "weapons": ("Akceleratory kinetyczne", "Atak +15% na poziom. Pancerz maszyn zmniejsza otrzymane obrażenia o 12%.", (610, 275, 175), 190),
        },
        "ships": {
            "scout": ("Sonda 01", "Opancerzony zwiadowca automatycznej sieci.", (125, 90, 40), 45, 2, 22, 10, 2, 1.5),
            "cargo": ("Holownik", "Ciężki transportowiec z kontenerami pancernymi.", (305, 135, 80), 95, 4, 75, 1600, 5, 0.8),
            "colonizer": ("Konstruktor", "Rozstawia modułowe fabryki i buduje nowy rdzeń.", (1960, 910, 530), 335, 3, 135, 600, 12, 0.6),
            "frigate": ("Młot", "Grafitowa platforma dział kinetycznych.", (430, 165, 105), 120, 31, 140, 80, 5, 0.9),
            "cruiser": ("Bastion", "Ciężka forteca orbitalna uzbrojona w akceleratory.", (1470, 685, 330), 285, 100, 470, 220, 14, 0.65),
        },
    },
}


# Keep unfamiliar racial unit names readable during the first mission.
SHIP_ROLES = {"scout": "Zwiadowca", "cargo": "Transportowiec", "colonizer": "Kolonizator",
              "frigate": "Lekki okręt bojowy", "cruiser": "Ciężki okręt bojowy"}
for _race in RACES.values():
    for _key, _spec in tuple(_race["ships"].items()):
        _race["ships"][_key] = (_spec[0], SHIP_ROLES[_key] + ". " + _spec[1], *_spec[2:])


def art_key(race_id, role):
    """Return a client-relative resource key, never a filesystem path."""
    return f"races/{race_id}/{role}" if race_id in RACES else ""


def public_race(race_id):
    """JSON-ready race choice data; the caller deep-copies nested balance rules."""
    import copy
    race = RACES[race_id]
    result = {key: race[key] for key in ("name", "description", "trait", "tradeoff", "weapon_name")}
    result.update(id=race_id, portrait_art=art_key(race_id, "portrait"),
                  colony_art=art_key(race_id, "colony"), weapon_art=art_key(race_id, "weapon"),
                  rules=copy.deepcopy(race["rules"]))
    return result
