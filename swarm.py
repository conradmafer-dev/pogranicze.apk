"""Khar is a non-playable, budgeted insect swarm, not a fourth player faction.

Only infected worlds synthesize the rare crystals used by the skill wheel. The
ordinary economy's `crystal` resource remains separate from `swarm_crystals`.
"""
from __future__ import annotations

OWNER_ID = "khar"
MAX_COLONIES = 36
CRYSTAL_CAPS = {"outpost": 36, "hive": 180}
CRYSTAL_HOURLY = {"outpost": 18, "hive": 54}
RAID_CRYSTALS = {"outpost": 12, "hive": 45}
RULES = {
    "production_multipliers": {"metal": 1.5, "crystal": 1.1, "fuel": 1.4},
    "energy_supply_per_level": 140,
    "energy_use_per_level": {"metal_mine": 18, "crystal_mine": 20, "refinery": 18},
    "first_volley_multiplier": 1.0, "regeneration_fraction": 0.0,
    "damage_reduction": 0.0,
}
BUILDINGS = {
    "metal_mine": ("Żerowisko żelaza", "Tysiące robotnic zeskrobują metal z powierzchni planety.", (90, 25, 0), 65),
    "crystal_mine": ("Komora krystalizacji", "Gromadzi zwykły kryształ; zakażona kolonia dodatkowo rodzi rzadkie Kryształy Roju.", (65, 45, 0), 70),
    "refinery": ("Trawieniec", "Rozkłada biomasę i skały na paliwo rojowych chmar.", (85, 35, 10), 70),
    "power_plant": ("Pulsujący odwłok", "Pulsująca tkanka dostarcza energię całemu gniazdu.", (70, 25, 10), 60),
    "shipyard": ("Wylęgarnia chmary", "Szybko wykluwa liczne, tanie organizmy próżniowe.", (140, 75, 25), 90),
    "lab": ("Węzeł feromonowy", "Koordynuje zasiewanie sąsiednich światów i wyprawy żuwaczy.", (120, 65, 20), 100),
}
RESEARCH = {
    "propulsion": ("Prąd chmary", "Chitynowe żagle niosą chmarę przez próżnię.", (100, 80, 45), 120),
    "weapons": ("Żuwacz kwasowy", "Chmara rozrywa kadłuby żuwaczkami i kwasem.", (130, 65, 35), 120),
}
SHIPS = {
    "scout": ("Czułek", "Mały owadzi zwiadowca wyczuwający nowe żerowiska.", (25, 20, 5), 20, 1, 5, 5, .3, 2.5),
    "cargo": ("Nosiciel", "Pękaty organizm zbierający zasoby dla ula.", (75, 35, 15), 35, 2, 30, 700, 1, 1.5),
    "colonizer": ("Zarodnia", "Rozsiewa jajeczka i chitynowe gniazda na wolnej planecie.", (260, 120, 70), 80, 1, 45, 80, 2, 1.7),
    "frigate": ("Żuwacz", "Tani owad bojowy; pojedynczy jest słaby, cała chmara potrafi zalać obronę.", (60, 25, 10), 30, 8, 20, 20, .5, 1.8),
    "cruiser": ("Królowa szturmowa", "Ciężki organizm osłaniający żuwacze i niosący kwasowe komory.", (500, 250, 100), 150, 65, 200, 200, 4, 1.1),
}
DESCRIPTION = "Owadzia chmara zasiewa nowe światy. Rozbijaj słabe przyczółki i przywoź Kryształy Roju, aby rozwijać koło umiejętności. Ule osłaniają znacznie liczniejsze chmary."


def kind(planet):
    return "hive" if planet.get("swarm_kind") == "hive" else "outpost"


def seed(planet, now, hive=False):
    """Set up a newly infected world. Initial map seeding is the only free stock.

    Later colonization arrives in a paid, real fleet; its seeded resources are the
    disassembled colonizer (as with player colonizers), not a recurring AI grant.
    """
    stage = "hive" if hive else "outpost"
    planet.update(owner_type="alien", owner_id=OWNER_ID, swarm_kind=stage,
                  swarm_crystals=90.0 if hive else 18.0, swarm_established_at=now,
                  swarm_next_attack_at=now + 300, swarm_suppressed_until=0)
    planet["buildings"] = {key: 2 if hive else 1 for key in BUILDINGS}
    planet["resources"] = {"metal": 2400.0 if hive else 450.0,
                           "crystal": 1600.0 if hive else 250.0,
                           "fuel": 900.0 if hive else 150.0}
    planet["ships"] = dict.fromkeys(SHIPS, 0)
    planet["ships"]["frigate"] = 24 if hive else 4
    planet["ships"]["colonizer"] = 1 if hive else 0


def public_planet(planet):
    stage = kind(planet)
    units = planet["ships"]
    power = sum(SHIPS[key][4] * value for key, value in units.items())
    threat = "Niska" if power <= 48 else "Średnia" if power <= 180 else "Wysoka"
    stock = int(planet.get("swarm_crystals", 0))
    hint = "zapas wyczerpany" if stock == 0 else "mały zapas" if stock < 12 else "zapas do zdobycia"
    return {"race_id": "swarm", "race_name": "Rój Khar", "colony_art": "swarm/colony",
            "planet_art": "swarm/planet", "swarm_kind": stage,
            "swarm_kind_name": "Ul Roju" if stage == "hive" else "Przyczółek Roju",
            "swarm_threat": threat, "swarm_crystals_hint": "Kryształy Roju: " + hint,
            "swarm_buildings": [{"key": key, "name": spec[0], "level": planet["buildings"][key],
                                 "art_key": "swarm/" + key} for key, spec in BUILDINGS.items()
                                if planet["buildings"][key] > 0]}
