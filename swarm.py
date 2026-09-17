"""Khar is a non-playable, budgeted insect swarm, not a fourth player faction.

Only infected worlds synthesize the rare crystals used by the skill wheel. The
ordinary economy's `crystal` resource remains separate from `swarm_crystals`.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t


OWNER_ID = "khar"
FORTRESS_VERSION = 2
MAX_COLONIES = 13
INITIAL_HIVES = 8
DAY_SECONDS = 24 * 3600
EXPANSION_SECONDS = 7 * DAY_SECONDS
ATTACK_SECONDS = DAY_SECONDS
RAID_INTERVAL_SECONDS = 2 * DAY_SECONDS
RAID_TARGET_INTERVAL_SECONDS = 4 * DAY_SECONDS
RAID_MIN_STOCK = 12_000
RAID_MIN_GAIN = 1_000
RAID_PARTY = {"frigate": 24, "cruiser": 2, "cargo": 4}
CRYSTAL_REGEN_SECONDS = 18 * 3600
MAX_BUILDING_LEVEL = 20
CRYSTAL_CAPS = {"outpost": 6, "hive": 6}
CRYSTAL_HOURLY = {"outpost": 1 / 18, "hive": 1 / 18}
RAID_CRYSTALS = {"outpost": 3, "hive": 3}
EXPANSION_ESCORT = {"frigate": 180, "cruiser": 30}
RULES = {
    "production_multipliers": {"metal": 1.5, "crystal": 1.1, "fuel": 1.4},
    "energy_supply_per_level": 140,
    "energy_use_per_level": {"metal_mine": 18, "crystal_mine": 20, "refinery": 18},
    "first_volley_multiplier": 1.0, "regeneration_fraction": 0.10,
    "damage_reduction": 0.15,
}
BUILDINGS = {
    "metal_mine": ("Żerowisko żelaza", "Tysiące robotnic zeskrobują metal z powierzchni planety.", (90, 25, 0), 65),
    "crystal_mine": ("Komora krystalizacji", "Gromadzi zwykły kryształ; zakażona kolonia dodatkowo rodzi rzadkie Kryształy Roju.", (65, 45, 0), 70),
    "refinery": ("Trawieniec", "Rozkłada biomasę i skały na paliwo rojowych chmar.", (85, 35, 10), 70),
    "power_plant": ("Pulsujący odwłok", "Pulsująca tkanka dostarcza energię całemu gniazdu.", (70, 25, 10), 60),
    "shipyard": ("Wylęgarnia chmary", "Wykluwa obronne chmary i ciężkie królowe, zużywając zasoby ula.", (140, 75, 25), 90),
    "lab": ("Węzeł feromonowy", "Rozwija uzbrojenie chmary. Każdy poziom zwiększa jej siłę ataku o 15%.", (120, 65, 20), 100),
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
DESCRIPTION = ("Nieliczne twierdze Roju rozbudowują gospodarkę i silną obronę. "
               "Rój może zajmować do 13 planet i sporadycznie wysyła wyprawy po zapasy graczy. "
               "Kryształ powstaje raz na 18 godzin rzeczywistych, tylko w obronionym gnieździe; zapas: do 6. "
               "Rozpoznaj cel i przygotuj kosztowną wyprawę, najlepiej wspólnie z innymi graczami.")


def kind(planet):
    return "hive" if planet.get("swarm_kind") == "hive" else "outpost"


def seed(planet, now, hive=False):
    """Initial fortresses receive a one-time starting economy and defending fleet.

    A later colony receives no generated ships or crystals: a paid colony ship
    becomes its initial infrastructure, while its real escort lands separately.
    """
    stage = "hive" if hive else "outpost"
    planet.update(owner_type="alien", owner_id=OWNER_ID, swarm_kind=stage,
                  swarm_crystals=3.0 if hive else 0.0, swarm_established_at=now,
                  swarm_next_attack_at=now + ATTACK_SECONDS, swarm_suppressed_until=0,
                  swarm_loot_sealed=False)
    planet["buildings"] = {key: (6 if key == "lab" else 8) if hive else 1 for key in BUILDINGS}
    planet["resources"] = {"metal": 18_000.0 if hive else 120.0,
                           "crystal": 12_000.0 if hive else 65.0,
                           "fuel": 8_000.0 if hive else 35.0}
    planet["ships"] = dict.fromkeys(SHIPS, 0)
    planet["queue"] = []
    if hive:
        planet["ships"].update(frigate=360, cruiser=60)


def weapon_level(planet):
    return max(0, min(MAX_BUILDING_LEVEL, int(planet.get("buildings", {}).get("lab", 0))))


def defense_targets(planet, now=None):
    """Budget targets grow with built facilities and real colony age, not visits.

    Age changes only the amount the AI tries to BUY, never adds free ships.
    Readiness below deliberately uses facilities alone: production during a
    settled offline interval must not silently cross an age threshold.
    """
    established = float(planet.get("swarm_established_at", now or 0))
    age_days = min(180, max(0, int(((now if now is not None else established) - established) // DAY_SECONDS)))
    yards = max(0, min(MAX_BUILDING_LEVEL, int(planet.get("buildings", {}).get("shipyard", 0))) - 8)
    return {"frigate": 360 + 60 * yards + 12 * age_days,
            "cruiser": 60 + 10 * yards + 2 * age_days}


def defense_minimum(planet):
    yards = max(0, min(MAX_BUILDING_LEVEL, int(planet.get("buildings", {}).get("shipyard", 0))) - 8)
    return {"frigate": 180 + 30 * yards, "cruiser": 30 + 5 * yards}


def ready(planet):
    return (planet.get("owner_id") == OWNER_ID
            and planet.get("buildings", {}).get("shipyard", 0) >= 1
            and all(planet.get("ships", {}).get(key, 0) >= amount
                    for key, amount in defense_minimum(planet).items()))


def public_planet(planet, now=None):
    stage = kind(planet)
    units = planet.get("ships", {})
    power = sum(SHIPS[key][4] * value for key, value in units.items() if key in SHIPS)
    power *= 1 + .15 * weapon_level(planet)
    defended = ready(planet)
    threat = t('Odbudowa obrony') if not defended else t('Ekstremalna') if power >= 20_000 else t('Bardzo wysoka')
    cap = CRYSTAL_CAPS[stage]
    stock_value = max(0.0, min(float(cap), float(planet.get("swarm_crystals", 0))))
    stock = int(stock_value)
    regenerating = defended and stock_value < cap
    next_at = (float(now) + (1 - (stock_value - stock)) * CRYSTAL_REGEN_SECONDS
               if regenerating and now is not None else 0)
    hint = t('Kryształy Roju: {0}/{1}').format(stock, cap)
    if not defended:
        hint += t(' · odnowa wstrzymana do odbudowy obrony')
    elif stock < cap:
        hint += t(" · +1 co 18 godz.")
    return {"race_id": "swarm", "race_name": t('Rój Khar'), "colony_art": "swarm/colony",
            "planet_art": "swarm/planet", "swarm_kind": stage,
            "swarm_kind_name": t('Twierdza Roju') if stage == "hive" else t('Gniazdo obronne'),
            "swarm_threat": threat, "swarm_threat_high": defended, "swarm_crystals_hint": hint,
            "swarm_crystals_stock": stock, "swarm_crystals_capacity": cap,
            "swarm_crystals_ready": defended, "swarm_crystals_regenerating": regenerating,
            "swarm_crystals_loot_available": (stock > 0 and units.get("frigate", 0) + units.get("cruiser", 0) > 0
                                              and (not planet.get("swarm_loot_sealed", False) or defended)),
            "swarm_crystals_next_at": next_at,
            "swarm_crystals_regen_seconds": CRYSTAL_REGEN_SECONDS,
            "swarm_weapon_level": weapon_level(planet),
            "swarm_buildings": [{"key": key, "name": t(spec[0]), "level": planet["buildings"].get(key, 0),
                                 "art_key": "swarm/" + key} for key, spec in BUILDINGS.items()
                                if planet["buildings"].get(key, 0) > 0]}
