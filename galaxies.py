"""Additive six-galaxy topology and authoritative intergalactic navigation.

Galactic map coordinates are illustrative. Costs use fixed catalogue coordinates,
never client data, and are prepaid for BOTH legs, just like local travel in 0.5.1.
"""
from __future__ import annotations

import math

try:
    from .i18n import t
    from . import swarm
except ImportError:
    from i18n import t
    import swarm

SYSTEMS_PER_GALAXY = 30
JUMP_BASE_FUEL = 1_000_000
JUMP_FUEL_PER_MASS = 40_000
JUMP_SECONDS_PER_MLY = 21_600
CATALOG = (
    {"id": "g1", "name": "Aurora", "x": 0.0, "y": 0.0, "art_key": "galaxies/aurora",
     "description": "Błękitna galaktyka macierzysta. Tutaj zaczynają nowe imperia."},
    {"id": "g2", "name": "Eclipse", "x": 1.0, "y": 0.0, "art_key": "galaxies/eclipse",
     "description": "Złote pasma pyłu otaczają ciemne jądro. Pierwszy cel dalekiej ekspansji."},
    {"id": "g3", "name": "Nexus", "x": -1.2, "y": 1.4, "art_key": "galaxies/nexus",
     "description": "Fioletowe ramiona i jasne jądro. Nowe układy czekają na kolonistów."},
    {"id": "g4", "name": "Omega", "x": 2.4, "y": 0.8, "art_key": "galaxies/omega",
     "description": "Czerwona spirala gwiazd. Wyprawa wymaga dużych rezerw paliwa."},
    {"id": "g5", "name": "Zephyr", "x": 0.0, "y": -3.0, "art_key": "galaxies/zephyr",
     "description": "Turkusowa galaktyka daleko od domu. Zaplanuj samodzielną kolonię."},
    {"id": "g6", "name": "Void", "x": 3.5, "y": -3.0, "art_key": "galaxies/void",
     "description": "Ciemne jądro na skraju znanej przestrzeni. Najdalsza wyprawa z Aurory."},
)
BY_ID = {g["id"]: g for g in CATALOG}


def separation(a: str, b: str) -> float:
    """Millions of fictional light-years; zero inside the same galaxy."""
    if a == b:
        return 0.0
    ga, gb = BY_ID[a], BY_ID[b]
    return max(1.0, math.hypot(ga["x"] - gb["x"], ga["y"] - gb["y"]))


def inferred_id(system_id: str) -> str:
    # Keeps all original s1..s30 identities. Newly allocated systems stay numeric.
    number = int(system_id[1:]) if system_id.startswith("s") and system_id[1:].isdigit() else 1
    return "g" + str(max(1, (number - 1) // SYSTEMS_PER_GALAXY + 1))


class UniverseMixin:
    def _ensure_universe(self, data=None):
        """Never erase/reseed existing worlds, players, accounts, queues or fleets.

        One fortress is seeded ONLY when a completely new galaxy is first added.
        Existing deadlines stay absolute. Migration is persisted by World.advance.
        """
        data = self.data if data is None else data
        for system in data["systems"]:
            system.setdefault("galaxy_id", "g1")
            for pid in system["planet_ids"]:
                data["planets"][pid].setdefault("galaxy_id", system["galaxy_id"])
        numeric = [int(s["id"][1:]) for s in data["systems"] if s["id"].startswith("s") and s["id"][1:].isdigit()]
        next_number = max(numeric, default=0) + 1
        home_names = [s["name"] for s in data["systems"] if s["galaxy_id"] == "g1"]
        for galaxy in CATALOG[1:]:
            if any(s["galaxy_id"] == galaxy["id"] for s in data["systems"]):
                continue
            new_systems = []
            for index in range(SYSTEMS_PER_GALAXY):
                sid = f"s{next_number}"
                next_number += 1
                suffix = home_names[index % len(home_names)] if home_names else str(index + 1)
                name = f"{galaxy['name']} {suffix}"
                planet_ids = []
                for slot in range(1, 4):
                    pid = f"{sid}p{slot}"
                    planet = self._planet(pid, f"{name} {slot}", sid, slot)
                    planet["galaxy_id"] = galaxy["id"]
                    data["planets"][pid] = planet
                    planet_ids.append(pid)
                new_systems.append({"id": sid, "name": name, "galaxy_id": galaxy["id"],
                                    "x": float(index % 6), "y": float(index // 6), "planet_ids": planet_ids})
            data["systems"].extend(new_systems)
            # Few strong hives, not a carpet of weak farmable targets. The global cap
            # allows five slow expansions beyond the eight initial fortresses.
            swarm.seed(data["planets"][new_systems[14]["planet_ids"][1]], self.now, hive=True)
        data["galaxy_schema_version"] = 1
        data["galaxies"] = [{"id": g["id"], "name": g["name"]} for g in CATALOG]

    def _galaxy_id(self, planet):
        return planet.get("galaxy_id", inferred_id(planet["system_id"]))

    def _route_details(self, origin, target):
        a, b = self._galaxy_id(origin), self._galaxy_id(target)
        distance = separation(a, b)
        return {"intergalactic": a != b, "origin_galaxy_id": a, "target_galaxy_id": b,
                "origin_galaxy_name": BY_ID[a]["name"], "target_galaxy_name": BY_ID[b]["name"],
                "distance_mly": round(distance, 3), "round_trip_fuel": True}

    def _public_galaxies(self, origin, player_id):
        result = []
        for g in CATALOG:
            systems = [s for s in self.data["systems"] if s["galaxy_id"] == g["id"]]
            planets = [self.data["planets"][pid] for s in systems for pid in s["planet_ids"]]
            distance = separation(self._galaxy_id(origin), g["id"])
            result.append({"id": g["id"], "name": g["name"], "description": t(g["description"]),
                           "art_key": g["art_key"], "systems_count": len(systems), "planets_count": len(planets),
                           "own_colonies": sum(p["owner_id"] == player_id for p in planets),
                           "hives_count": sum(p["owner_id"] == swarm.OWNER_ID for p in planets),
                           "distance_mly": round(distance, 3),
                           "minimum_jump_fuel": math.ceil(distance * JUMP_BASE_FUEL)})
        return result
