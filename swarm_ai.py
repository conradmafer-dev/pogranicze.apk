"""Slow fortress-focused Khar decisions, sharing normal queues and fleet events.

All clocks use World.now. The seven-day colony gate and two-day global resource raids
are real seconds even on an accelerated test server. Growth spends the same
ordinary resources as players and ships only appear on queue completion.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t

import math
import secrets

try:
    from . import swarm
except ImportError:  # Railway ships these modules next to app.py.
    import swarm

RESOURCES = ("metal", "crystal", "fuel")


class SwarmAIMixin:
    @staticmethod
    def _swarm_ready(planet):
        return swarm.ready(planet)

    @staticmethod
    def _swarm_weapon_level(planet):
        return swarm.weapon_level(planet)

    def _swarm_launch(self, origin, target, mission, ships, *, raid=False):
        """Private launcher also enforces strategic guards so callers cannot skip them."""
        if (origin.get("owner_id") != swarm.OWNER_ID or target["id"] == origin["id"]
                or mission not in ("colonize", "attack") or not isinstance(ships, dict)
                or set(ships) - set(swarm.SHIPS)
                or any(type(n) is not int or n < 0 for n in ships.values())):
            return None
        ships = {key: ships.get(key, 0) for key in swarm.SHIPS}
        if not sum(ships.values()) or any(n > origin["ships"].get(k, 0) for k, n in ships.items()):
            return None
        planets = list(self.data["planets"].values())
        alien = self.data["alien"]
        pending = [f for f in self.data["fleets"].values()
                   if f["owner_id"] == swarm.OWNER_ID and f["mission"] == "colonize"
                   and f["status"] == "outbound"]
        if raid and mission != "attack":
            return None
        if mission == "colonize":
            deadline = alien.setdefault("swarm_next_colonization_at", self.now + swarm.EXPANSION_SECONDS)
            if (self.now < deadline or pending or target["owner_type"] != "empty"
                    or sum(p["owner_id"] == swarm.OWNER_ID for p in planets) >= swarm.MAX_COLONIES
                    or ships["colonizer"] < 1
                    or any(ships[k] < n for k, n in swarm.EXPANSION_ESCORT.items())):
                return None
        elif raid:
            expected_party = {key: swarm.RAID_PARTY.get(key, 0) for key in swarm.SHIPS}
            deadline = alien.setdefault("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
            if (ships != expected_party or self.now < deadline
                    or self._swarm_raid_score(origin, target, ships) <= 0
                    or any(f["owner_id"] == swarm.OWNER_ID and f["mission"] == "attack"
                           and f["status"] == "outbound" for f in self.data["fleets"].values())):
                return None
        else:
            # Even an empty world already reserved by another colony fleet counts.
            # Reaching our colony cap never turns peaceful empty space into a war.
            if (any(p["owner_type"] == "empty" for p in planets)
                    or target["owner_type"] != "player"
                    or self._player(target["owner_id"])["protected_until"] > self.now
                    or origin.get("swarm_next_attack_at", 0) > self.now):
                return None
        minimum = swarm.defense_minimum(origin)
        if any(origin["ships"][k] - ships[k] < n for k, n in minimum.items()):
            return None
        seconds, fuel = self._flight_numbers(origin, target, ships)
        if origin["resources"]["fuel"] < fuel:
            return None
        origin["resources"]["fuel"] -= fuel
        for key, amount in ships.items():
            origin["ships"][key] -= amount
        fleet = {"id": "f" + secrets.token_hex(8), "owner_id": swarm.OWNER_ID,
                 "race_id": "swarm", "origin_id": origin["id"], "target_id": target["id"],
                 "mission": mission, "status": "outbound", "ships": ships,
                 "cargo": dict.fromkeys(RESOURCES, 0), "swarm_crystals": 0,
                 "swarm_weapon_level": self._swarm_weapon_level(origin),
                 "started_at": self.now, "seconds": seconds, "arrives_at": self.now + seconds}
        if raid:
            fleet["swarm_raid"] = True
        self.data["fleets"][fleet["id"]] = fleet
        if mission == "colonize":
            # Charged at departure, even if intercepted or the colony fails to land.
            alien["swarm_next_colonization_at"] = self.now + swarm.EXPANSION_SECONDS
        elif raid:
            alien["swarm_next_raid_at"] = self.now + swarm.RAID_INTERVAL_SECONDS
            self._player(target["owner_id"])["swarm_raid_protected_until"] = self.now + swarm.RAID_TARGET_INTERVAL_SECONDS
            origin["swarm_next_attack_at"] = self.now + swarm.ATTACK_SECONDS
        else:
            origin["swarm_next_attack_at"] = self.now + swarm.ATTACK_SECONDS
        return fleet

    def _swarm_raid_score(self, origin, target, ships):
        """Conservative stock/fuel estimate, not a promise of victory or loot.

        Only the three ordinary resources count. The player's scarce skill
        currency is never a reason for a raid and never part of its cargo.
        """
        if self._galaxy_id(origin) != self._galaxy_id(target):
            return 0
        if target.get("owner_type") != "player":
            return 0
        player = self._player(target["owner_id"])
        if (player["protected_until"] > self.now
                or player.get("swarm_raid_protected_until", 0) > self.now):
            return 0
        stock = sum(target["resources"][key] for key in RESOURCES)
        if stock < swarm.RAID_MIN_STOCK:
            return 0
        capacity = sum(swarm.SHIPS[key][6] * amount for key, amount in ships.items())
        _, fuel = self._flight_numbers(origin, target, ships)
        available = min(capacity, sum(self._lootable_resources(target).values()))
        gain = available - 3 * fuel
        if gain < swarm.RAID_MIN_GAIN:
            return 0
        attack = self._power(ships, self._swarm_weapon_level(origin), swarm.SHIPS)
        defense = self._power(target["ships"], player["research"]["weapons"], self._specs(target["owner_id"], "ships"))
        # Leave heavily defended worlds alone; ordinary battle rules still decide
        # the outcome after travel, including reinforcements and racial effects.
        if defense > attack * 1.1:
            return 0
        return gain

    def _swarm_queue(self, planet, kind, key, amount=1):
        """Pay before queueing; repeated AI visits never grant finished units."""
        if (planet.get("owner_id") != swarm.OWNER_ID or planet["queue"]
                or kind not in ("ship", "build") or type(amount) is not int
                or not 1 <= amount <= 1000):
            return False
        specs = swarm.SHIPS if kind == "ship" else swarm.BUILDINGS
        if key not in specs:
            return False
        if kind == "ship" and planet["buildings"]["shipyard"] < (2 if key == "cruiser" else 1):
            kind, key, amount, specs = "build", "shipyard", 1, swarm.BUILDINGS
        if kind == "build":
            amount = 1
        level = 0 if kind == "ship" else planet["buildings"][key]
        if kind == "build" and level >= swarm.MAX_BUILDING_LEVEL:
            return False
        spec = specs[key]
        costs = {k: math.ceil(value * 1.65 ** level) * amount
                 for k, value in zip(RESOURCES, spec[2])}
        if any(planet["resources"][k] < cost for k, cost in costs.items()):
            return False
        for key_resource, cost in costs.items():
            planet["resources"][key_resource] -= cost
        duration = max(1, math.ceil(spec[3] * 1.3 ** level * amount / self.speed))
        planet["queue"].append({"id": "q" + secrets.token_hex(8), "kind": kind,
                                "key": key, "amount": amount, "level": level + 1,
                                "started_at": self.now, "seconds": duration,
                                "ends_at": self.now + duration})
        return True

    def _swarm_train_to(self, planet, targets):
        """Buy at most one affordable batch, prioritizing proportional shortages."""
        candidates = sorted(targets, key=lambda key: (planet["ships"][key] / max(1, targets[key]), key))
        for key in candidates:
            missing = targets[key] - planet["ships"][key]
            if missing <= 0:
                continue
            batch = min(missing, 24 if key == "frigate" else 4)
            spec = swarm.SHIPS[key]
            affordable = min((int(planet["resources"][resource] // cost)
                              for resource, cost in zip(RESOURCES, spec[2]) if cost > 0),
                             default=batch)
            if affordable > 0 and self._swarm_queue(planet, "ship", key, min(batch, affordable)):
                return True
        return False

    def _swarm_grow_economy(self, planet):
        """Facility growth is bounded by age and budget, while repairs come first."""
        age = max(0, self.now - planet.get("swarm_established_at", self.now))
        desired = min(swarm.MAX_BUILDING_LEVEL, 8 + int(age // (12 * 3600)))
        desired_lab = min(swarm.MAX_BUILDING_LEVEL, 6 + int(age // swarm.DAY_SECONDS))
        buildings = planet["buildings"]
        if self.energy(planet)["factor"] < 1 and buildings["power_plant"] < swarm.MAX_BUILDING_LEVEL:
            if self._swarm_queue(planet, "build", "power_plant"):
                return True
        priorities = ("metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab")
        candidates = [key for key in priorities
                      if buildings[key] < (desired_lab if key == "lab" else desired)]
        candidates.sort(key=lambda key: (buildings[key] / (desired_lab if key == "lab" else desired), priorities.index(key)))
        for key in candidates:
            if self._swarm_queue(planet, "build", key):
                return True
        return False

    def _alien_turn(self):
        planets = list(self.data["planets"].values())
        colonies = sorted((p for p in planets if p["owner_id"] == swarm.OWNER_ID), key=lambda p: p["id"])
        alien = self.data["alien"]
        alien.setdefault("swarm_next_colonization_at", self.now + swarm.EXPANSION_SECONDS)
        alien.setdefault("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
        empty = [p for p in planets if p["owner_type"] == "empty"]
        pending = [f for f in self.data["fleets"].values()
                   if f["owner_id"] == swarm.OWNER_ID and f["mission"] == "colonize" and f["status"] == "outbound"]
        for planet in colonies:
            if planet["queue"]:
                continue
            # A new strong escort settles immediately; becoming a full hive never
            # grants stock or ships. It merely reflects completed infrastructure.
            if (swarm.kind(planet) == "outpost" and self._swarm_ready(planet)
                    and min(planet["buildings"].values()) >= 6):
                planet["swarm_kind"] = "hive"
            if not self._swarm_ready(planet):
                if self._swarm_train_to(planet, swarm.defense_minimum(planet)):
                    continue
            if self._swarm_grow_economy(planet):
                continue
            targets = swarm.defense_targets(planet, self.now)
            if self._swarm_train_to(planet, targets):
                continue
            if any(planet["ships"][key] < count for key, count in targets.items()):
                continue
            # Colony count, travel reservations and the global clock are checked
            # again by the launcher. One eligible hive can launch per seven days.
            expand = (empty and not pending and len(colonies) < swarm.MAX_COLONIES
                      and self.now >= alien["swarm_next_colonization_at"]
                      and self.now - planet.get("swarm_established_at", self.now) >= swarm.EXPANSION_SECONDS)
            attack_targets = []
            if (self.now >= alien["swarm_next_raid_at"]
                    and not any(f["owner_id"] == swarm.OWNER_ID and f["mission"] == "attack"
                                and f["status"] == "outbound" for f in self.data["fleets"].values())):
                targeted = {f["target_id"] for f in self.data["fleets"].values()
                            if f["owner_id"] == swarm.OWNER_ID and f["mission"] == "attack" and f["status"] == "outbound"}
                attack_targets = [p for p in planets if p["owner_type"] == "player"
                                  and p["id"] not in targeted
                                  and self._swarm_raid_score(planet, p, swarm.RAID_PARTY) > 0]
            if not expand and not attack_targets:
                continue
            # Build the real escort/expedition ON TOP of the home defense target.
            expedition = swarm.EXPANSION_ESCORT if expand else swarm.RAID_PARTY
            surplus = {key: targets.get(key, 0) + count for key, count in expedition.items()}
            if self._swarm_train_to(planet, surplus):
                continue
            if any(planet["ships"][key] < count for key, count in surplus.items()):
                continue
            if expand and planet["ships"]["colonizer"] < 1:
                self._swarm_queue(planet, "ship", "colonizer")
                continue
            candidates = [p for p in empty if self._galaxy_id(p) == self._galaxy_id(planet)] if expand else attack_targets
            if not candidates:
                continue
            target = (min(candidates, key=lambda p: (self._distance(planet, p), p["id"])) if expand
                      else max(candidates, key=lambda p: (self._swarm_raid_score(planet, p, swarm.RAID_PARTY), p["id"])))
            ships = dict.fromkeys(swarm.SHIPS, 0)
            ships.update(expedition)
            ships["colonizer"] = 1 if expand else 0
            fleet = self._swarm_launch(planet, target, "colonize" if expand else "attack", ships, raid=not expand)
            if fleet:
                if expand:
                    pending.append(fleet)
                    for player_id in self.data["players"]:
                        self._report(player_id, t('Ekspansja Roju'), t('Silnie osłaniana zarodnia wyruszyła z {0} na {1}.').format(planet['name'], target['name']), "swarm/colonizer")
                else:
                    self._report(target["owner_id"], t('Najazd Roju po surowce'), t('Transportowce Roju z eskortą lecą z {0} na {1} po zapasy. Przybędą za {2} s.').format(planet['name'], target['name'], fleet['seconds']), "swarm/weapon")
