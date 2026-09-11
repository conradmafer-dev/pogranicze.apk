#!/usr/bin/env python3
"""Pogranicze Galaktyki: authoritative, dependency-free multiplayer test server."""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import secrets
import signal
import sqlite3
import threading
import time
import unicodedata
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

try:  # Both `python -m server.main` and Railway's direct app.py import work.
    from .races import NEUTRAL_RULES, RACES, art_key, public_race
    from . import skill_tree, swarm
except ImportError:
    from races import NEUTRAL_RULES, RACES, art_key, public_race
    import skill_tree, swarm

VERSION = "0.2.0"
UPDATE_DEFAULT_VERSION = "0.1.5"
CLIENT_VERSION_CODE = 6
MAX_VERSION_CODE = 2_100_000_000
MAX_APK_SIZE_BYTES = 268_435_456
RESOURCES = ("metal", "crystal", "fuel")
BUILDINGS = {
    "metal_mine": ("Kopalnia metalu", "Metal do budowy imperium.", (200, 70, 0), 120),
    "crystal_mine": ("Kopalnia kryształów", "Kryształy do badań i elektroniki.", (150, 110, 0), 150),
    "refinery": ("Rafineria", "Paliwo dla twoich flot.", (220, 130, 0), 180),
    "power_plant": ("Elektrownia", "Energia zasila wydobycie.", (180, 80, 0), 120),
    "shipyard": ("Stocznia", "Buduje statki. Poziom 2 odblokowuje krążownik.", (400, 230, 80), 240),
    "lab": ("Laboratorium", "Pozwala ulepszać napęd i uzbrojenie.", (350, 280, 80), 240),
}
RESEARCH = {
    "propulsion": ("Napęd", "Każdy poziom przyspiesza podróże o 15%.", (350, 400, 200), 240),
    "weapons": ("Uzbrojenie", "Każdy poziom zwiększa siłę ataku o 15%.", (500, 300, 150), 240),
}
SHIPS = {
    # name, description, cost, build seconds, attack, hull, hold, fuel, speed
    "scout": ("Zwiadowca", "Odkrywa zasoby i obronę planety.", (100, 100, 30), 60, 2, 15, 10, 1, 1.8),
    "cargo": ("Transportowiec", "Przewozi zapasy i zdobycz.", (250, 150, 60), 120, 3, 50, 1500, 3, 1.0),
    "colonizer": ("Kolonizator", "Zakłada kolonię na wolnej planecie.", (1600, 1000, 400), 420, 2, 90, 600, 8, 0.8),
    "frigate": ("Fregata", "Podstawowy okręt bojowy.", (350, 180, 80), 150, 28, 95, 80, 3, 1.2),
    "cruiser": ("Krążownik", "Ciężki okręt do przełamywania obrony.", (1200, 750, 250), 360, 90, 320, 220, 9, 0.85),
}
SYSTEM_NAMES = ["Helios", "Vega", "Orion", "Lyra", "Nadir", "Aster", "Talos", "Iris", "Atlas", "Selene", "Draco", "Aurora", "Kronos", "Eos", "Polaris", "Mira", "Nexus", "Arden", "Ereb", "Cygnus", "Boreas", "Zefir", "Tytan", "Perseusz", "Arka", "Solara", "Kepler", "Andara", "Vesper", "Rubież"]
MAX_RESOURCE = 10_000_000
MAX_BODY = 16_384
MAX_COLONIES = 3


class GameError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def validate_download_url(value):
    """Check an ASCII HTTPS DNS download link; same subset as the Android client."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("PGR_DOWNLOAD_URL: podaj adres HTTPS do 2048 znaków.")
    if not value:
        return ""
    if (any(ord(c) <= 32 or ord(c) >= 127 for c in value) or "\\" in value
            or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f|5c)", value, re.IGNORECASE)):
        raise ValueError("PGR_DOWNLOAD_URL: adres zawiera niedozwolone znaki.")
    try:
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?(?:[/?].*)?", value):
            raise ValueError
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
        if (parsed.scheme != "https" or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment or "#" in value
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            labels = host.split(".")
            if (len(host) > 253 or len(labels) < 2
                    or not all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part)
                               for part in labels)
                    or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]*", labels[-1])
                    or labels[-1].lower() in ("localhost", "local", "internal", "lan", "home", "test", "invalid", "example", "onion")
                    or host.lower() == "home.arpa" or host.lower().endswith(".home.arpa")):
                raise ValueError
        else:
            raise ValueError
    except ValueError:
        raise ValueError("PGR_DOWNLOAD_URL: wymagany publiczny adres HTTPS bez hasła ani fragmentu #.") from None
    return value


class UpdatePolicy:
    """Startup configuration; it neither changes nor migrates any game save."""

    def __init__(self, latest_version_code=CLIENT_VERSION_CODE, latest_version=UPDATE_DEFAULT_VERSION,
                 min_version_code=0, download_url="", message="",
                 apk_sha256="", apk_size_bytes=0):
        for name, value in (("PGR_LATEST_VERSION_CODE", latest_version_code),
                            ("PGR_MIN_VERSION_CODE", min_version_code)):
            if type(value) is not int or not 0 <= value <= MAX_VERSION_CODE:
                raise ValueError(f"{name}: podaj liczbę całkowitą od 0 do {MAX_VERSION_CODE}.")
        if latest_version_code < min_version_code:
            raise ValueError("PGR_LATEST_VERSION_CODE nie może być mniejsze od PGR_MIN_VERSION_CODE.")
        for name, value, limit in (("PGR_LATEST_VERSION", latest_version, 40),
                                   ("PGR_UPDATE_MESSAGE", message, 300)):
            if (not isinstance(value, str) or len(value) > limit
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError(f"{name}: maksymalnie {limit} znaków, bez znaków sterujących.")
        if not latest_version.strip():
            raise ValueError("PGR_LATEST_VERSION nie może być puste.")
        download_url = validate_download_url(download_url)
        if (not isinstance(apk_sha256, str)
                or (apk_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", apk_sha256))):
            raise ValueError("PGR_APK_SHA256: podaj 64 znaki szesnastkowe SHA-256 albo pozostaw puste.")
        if type(apk_size_bytes) is not int or not 0 <= apk_size_bytes <= MAX_APK_SIZE_BYTES:
            raise ValueError(f"PGR_APK_SIZE_BYTES: podaj liczbę całkowitą od 0 do {MAX_APK_SIZE_BYTES}.")
        if bool(apk_sha256) != bool(apk_size_bytes):
            raise ValueError("Ustaw razem PGR_APK_SHA256 i dodatnie PGR_APK_SIZE_BYTES.")
        if apk_sha256 and not download_url:
            raise ValueError("Ustaw PGR_DOWNLOAD_URL razem z danymi pliku APK.")
        if min_version_code > 0 and not download_url:
            raise ValueError("Ustaw PGR_DOWNLOAD_URL przed wymaganiem aktualizacji (PGR_MIN_VERSION_CODE > 0).")
        self.latest_version_code = latest_version_code
        self.latest_version = latest_version
        self.min_version_code = min_version_code
        self.download_url = download_url
        self.message = message
        self.apk_sha256 = apk_sha256.lower()
        self.apk_size_bytes = apk_size_bytes

    def manifest(self):
        return {"ok": True, "latest_version_code": self.latest_version_code,
                "latest_version": self.latest_version, "min_version_code": self.min_version_code,
                "download_url": self.download_url, "message": self.message,
                "apk_sha256": self.apk_sha256, "apk_size_bytes": self.apk_size_bytes}


def load_update_policy(env=None):
    """Read environment once at startup; build_server stays injectable for tests."""
    env = os.environ if env is None else env

    def version_code(name, default):
        value = env.get(name, str(default))
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value):
            raise ValueError(f"{name}: podaj nieujemną liczbę całkowitą.")
        return int(value)

    return UpdatePolicy(latest_version_code=version_code("PGR_LATEST_VERSION_CODE", CLIENT_VERSION_CODE),
                        latest_version=env.get("PGR_LATEST_VERSION", UPDATE_DEFAULT_VERSION),
                        min_version_code=version_code("PGR_MIN_VERSION_CODE", 0),
                        download_url=env.get("PGR_DOWNLOAD_URL", ""),
                        message=env.get("PGR_UPDATE_MESSAGE", ""),
                        apk_sha256=env.get("PGR_APK_SHA256", ""),
                        apk_size_bytes=version_code("PGR_APK_SIZE_BYTES", 0))


class UpdateRequired(GameError):
    def __init__(self, policy):
        super().__init__("Zaktualizuj grę, aby kontynuować.", 426)
        self.update = policy.manifest()


def ident(prefix):
    return prefix + secrets.token_hex(8)


def integer(value, label, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise GameError(f"{label}: podaj liczbę całkowitą od {low} do {high}.")
    return value


def counts(value, valid_keys, label, maximum=1_000_000):
    if not isinstance(value, dict) or any(k not in valid_keys for k in value):
        raise GameError(f"Nieprawidłowe dane: {label}.")
    return {k: integer(value.get(k, 0), label, 0, maximum) for k in valid_keys}


def scaled_cost(base, level):
    return dict(zip(RESOURCES, [int(math.ceil(v * 1.65 ** level)) for v in base]))


def affordable(planet, cost):
    return all(planet["resources"][k] >= v for k, v in cost.items())


def spend(planet, cost):
    for k, v in cost.items():
        planet["resources"][k] -= v


def blank_ships():
    return dict.fromkeys(SHIPS, 0)


def fleet_capacity(specs, ships):
    # Stat bonuses have at most six decimal places. Remove binary floating-point
    # noise before flooring the combined hold, without rounding real fractions up.
    return math.floor(round(math.fsum(specs[key][6] * n for key, n in ships.items()), 6))


class World:
    """All public operations are locked. advance(now) makes time injectable in tests."""

    def __init__(self, db_path="galaxy.sqlite3", speed=10.0, now=None,
                 max_players=0):
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.1 <= speed <= 1000:
            raise ValueError("speed must be finite and between 0.1 and 1000")
        if type(max_players) is not int or max_players < 0:
            raise ValueError("max_players must be a nonnegative integer (0 disables the account cap)")
        self.max_players = max_players
        self.speed = float(speed)
        self.lock = threading.RLock()
        self.now = float(time.time() if now is None else now)
        if str(db_path) != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(str(db_path))), exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, name_key TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, player_id TEXT NOT NULL REFERENCES accounts(id), expires REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_player ON sessions(player_id);
        """)
        row = self.db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
        if row:
            self.data = json.loads(row[0])
            self.now = max(self.now, self.data["last_update"])
            self._ensure_progression()
            # Existing absolute event deadlines remain valid if speed is changed.
            self.advance(self.now)
        else:
            self.data = self._new_world()
            self._save()

    def _new_world(self):
        systems, planets = [], {}
        for i, name in enumerate(SYSTEM_NAMES):
            sid = f"s{i+1}"
            ids = []
            for slot in range(1, 4):
                pid = f"{sid}p{slot}"
                ids.append(pid)
                planets[pid] = self._planet(pid, f"{name} {slot}", sid, slot)
            systems.append({"id": sid, "name": name, "x": (i % 6) * 1.0, "y": (i // 6) * 1.0, "planet_ids": ids})
        for sid in ("s14", "s15", "s20"):
            swarm.seed(planets[f"{sid}p2"], self.now, hive=True)
        # Weak peripheral nests remain approachable with every faction's starter fleet.
        for sid in ("s2", "s6", "s25", "s29"):
            swarm.seed(planets[f"{sid}p2"], self.now)
        return {"progression_version": 1, "last_update": self.now, "systems": systems, "planets": planets, "players": {}, "fleets": {}, "alien": {"name": "Rój Khar", "next_expansion_at": self.now + 12}}

    def _ensure_progression(self):
        """Additive migration: no wallet grant, and existing race signatures stay active."""
        for player in self.data["players"].values():
            player.setdefault("swarm_crystals", 0)
            player["skill_nodes"] = skill_tree.unlocked_for(player.get("race_id", ""), player.get("skill_nodes", []))
        if self.data.get("progression_version", 0) < 1:
            # One-time NPC frontier rebuild also gives upgraded servers real hives.
            # Player accounts/worlds remain intact; old NPC ships/queues are retired.
            for fid, fleet in list(self.data["fleets"].items()):
                if fleet["owner_id"] == "khar":
                    del self.data["fleets"][fid]
            for pid, planet in list(self.data["planets"].items()):
                if planet["owner_id"] == "khar":
                    self.data["planets"][pid] = self._planet(pid, planet["name"], planet["system_id"], planet["slot"])
            for preferred, hive in (("s14p2", True), ("s15p2", True), ("s20p2", True),
                                     ("s2p2", False), ("s6p2", False), ("s25p2", False), ("s29p2", False)):
                reference = self.data["planets"][preferred]
                empty = [p for p in self.data["planets"].values() if p["owner_type"] == "empty"]
                if not empty:
                    break
                planet = reference if reference["owner_type"] == "empty" else min(empty, key=lambda p: self._distance(reference, p))
                swarm.seed(planet, self.now, hive=hive)
            self.data["alien"]["next_expansion_at"] = self.now + 12
            self.data["progression_version"] = 1

    @staticmethod
    def _planet(pid, name, sid, slot):
        return {"id": pid, "name": name, "system_id": sid, "slot": slot, "owner_type": "empty", "owner_id": "", "resources": dict.fromkeys(RESOURCES, 0.0), "buildings": dict.fromkeys(BUILDINGS, 0), "ships": blank_ships(), "queue": []}

    def _save(self, commit=True):
        body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        self.db.execute("INSERT INTO snapshot(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (body,))
        if commit:
            self.db.commit()

    def close(self):
        with self.lock:
            self._save()
            self.db.close()

    def _race_id(self, owner_id):
        # Khar is an NPC without a skill root; its own catalog is handled in _specs.
        race_id = self.data["players"].get(owner_id, {}).get("race_id", "")
        return race_id if isinstance(race_id, str) and race_id in RACES else ""

    def _bonuses(self, owner_id):
        player = self.data["players"].get(owner_id, {})
        return skill_tree.bonuses(self._race_id(owner_id), player.get("skill_nodes", []))

    def _rules(self, owner_id):
        if owner_id == "khar":
            return swarm.RULES
        race_id = self._race_id(owner_id)
        rules = copy.deepcopy(RACES[race_id]["rules"] if race_id else NEUTRAL_RULES)
        bonuses = self._bonuses(owner_id)
        # Signatures now come from roots exactly once; foreign roots can be earned.
        rules["first_volley_multiplier"] = 1.0 + bonuses.get("first_volley", 0)
        rules["regeneration_fraction"] = bonuses.get("regeneration", 0)
        rules["damage_reduction"] = bonuses.get("damage_reduction", 0)
        for resource in RESOURCES:
            rules["production_multipliers"][resource] *= 1.0 + bonuses.get("production_" + resource, 0)
        rules["energy_supply_per_level"] *= 1.0 + bonuses.get("energy", 0)
        return rules

    def _specs(self, owner_id, group):
        if owner_id == "khar":
            return {"buildings": swarm.BUILDINGS, "ships": swarm.SHIPS, "research": swarm.RESEARCH}[group]
        race_id = self._race_id(owner_id)
        specs = RACES[race_id][group] if race_id else {"buildings": BUILDINGS, "ships": SHIPS, "research": RESEARCH}[group]
        if group != "ships":
            return specs
        bonuses = self._bonuses(owner_id)
        result = {}
        for key, spec in specs.items():
            values = list(spec)
            for index, effect in ((4, "attack"), (5, "hull"), (6, "capacity"), (8, "flight_speed")):
                values[index] = round(values[index] * (1.0 + bonuses.get(effect, 0)), 6)
            values[7] = round(values[7] * (1.0 - bonuses.get("fuel_efficiency", 0)), 6)
            result[key] = tuple(values)
        return result

    def _race_choice_reason(self, player_id):
        if self._race_id(player_id):
            return "Rasa tego imperium została już wybrana."
        owned_ids = {p["id"] for p in self.data["planets"].values() if p["owner_id"] == player_id}
        if any(p["queue"] for p in self.data["planets"].values() if p["id"] in owned_ids):
            return "Poczekaj na zakończenie wszystkich projektów przed wyborem rasy."
        if any(f["owner_id"] == player_id or f["target_id"] in owned_ids for f in self.data["fleets"].values()):
            return "Poczekaj na zakończenie własnych lotów i misji do twoich planet przed wyborem rasy."
        return ""

    def energy(self, p):
        b = p["buildings"]
        rules = self._rules(p["owner_id"])
        supply = b["power_plant"] * rules["energy_supply_per_level"]
        used = sum(b[key] * amount for key, amount in rules["energy_use_per_level"].items())
        return {"supply": supply, "used": used, "factor": min(1.0, supply / used) if used else 1.0}

    def production(self, p):
        factor = self.energy(p)["factor"] * self.speed
        multipliers = self._rules(p["owner_id"])["production_multipliers"]
        return {resource: (base + p["buildings"][key] * per_level) * factor * multipliers[resource]
                for resource, key, base, per_level in (("metal", "metal_mine", 90, 450),
                                                      ("crystal", "crystal_mine", 60, 330),
                                                      ("fuel", "refinery", 30, 180))}

    def _produce(self, dt):
        if dt <= 0:
            return
        for p in self.data["planets"].values():
            if p["owner_type"] != "empty":
                for k, rate in self.production(p).items():
                    p["resources"][k] = min(MAX_RESOURCE, p["resources"][k] + rate * dt / 3600)
                if p["owner_id"] == "khar":
                    stage = swarm.kind(p)
                    p["swarm_crystals"] = min(swarm.CRYSTAL_CAPS[stage], p.get("swarm_crystals", 0) + swarm.CRYSTAL_HOURLY[stage] * self.speed * dt / 3600)

    def advance(self, now=None):
        """Set real UNIX time, settle existing events in order, then one NPC decision.

        Offline production and scheduled flights complete exactly once. NPC decisions
        are deliberately not replayed over the offline interval, avoiding instant
        galaxy-wide colonization after a server restart.
        """
        with self.lock:
            now = float(time.time() if now is None else now)
            if not math.isfinite(now):
                raise ValueError("now must be finite")
            now = max(now, self.data["last_update"])
            cursor = self.data["last_update"]
            while True:
                deadlines = [p["queue"][0]["ends_at"] for p in self.data["planets"].values() if p["queue"]]
                deadlines.extend(f["arrives_at"] for f in self.data["fleets"].values())
                deadline = min(deadlines, default=float("inf"))
                if deadline > now:
                    break
                event_time = max(cursor, deadline)
                self._produce(event_time - cursor)
                cursor = event_time
                self.now = event_time
                for p in self.data["planets"].values():
                    if p["queue"] and p["queue"][0]["ends_at"] <= event_time:
                        self._complete_queue(p)
                for fid in list(self.data["fleets"]):
                    fleet = self.data["fleets"].get(fid)
                    if fleet and fleet["arrives_at"] <= event_time:
                        self._complete_fleet(fleet)
            self._produce(now - cursor)
            self.now = now
            self.data["last_update"] = now
            if now >= self.data["alien"]["next_expansion_at"]:
                self._alien_turn()
                self.data["alien"]["next_expansion_at"] = now + max(8, 120 / self.speed)
            self.db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            self._save()

    def _complete_queue(self, p):
        task = p["queue"].pop(0)
        if task["kind"] == "build":
            p["buildings"][task["key"]] = task["level"]
        elif task["kind"] == "ship":
            p["ships"][task["key"]] += task["amount"]
        else:
            player = self.data["players"][p["owner_id"]]
            player["research"][task["key"]] = task["level"]
        if p["owner_type"] == "player":
            names = self._specs(p["owner_id"], {"build": "buildings", "ship": "ships", "research": "research"}[task["kind"]])
            self._report(p["owner_id"], "Ukończono projekt", f"{p['name']}: {names[task['key']][0]}" + (f" ×{task['amount']}." if task["kind"] == "ship" else f", poziom {task['level']}."))

    @staticmethod
    def _credentials(name, password):
        if not isinstance(name, str) or not isinstance(password, str):
            raise GameError("Podaj nazwę i hasło.")
        name = unicodedata.normalize("NFKC", name.strip())
        if not 3 <= len(name) <= 20 or not all(c.isalnum() or c in " _-" for c in name):
            raise GameError("Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -.")
        if not 8 <= len(password) <= 128:
            raise GameError("Hasło musi mieć 8–128 znaków.")
        return name, password

    @staticmethod
    def _password_hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 240_000).hex()

    def _session(self, player_id):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.db.execute("INSERT INTO sessions VALUES(?,?,?)", (token_hash, player_id, self.now + 30 * 86400))
        self.db.execute("DELETE FROM sessions WHERE player_id=? AND token_hash NOT IN (SELECT token_hash FROM sessions WHERE player_id=? ORDER BY expires DESC LIMIT 10)", (player_id, player_id))
        return token

    def register(self, name, password, invite=""):
        # Older clients may still send an invitation; registration is now open.
        # The legacy field is deliberately ignored and never stored or returned.
        name, password = self._credentials(name, password)
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(password, salt)
        with self.lock:
            if self.db.execute("SELECT 1 FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone():
                raise GameError("Ta nazwa jest już zajęta.", 409)
            if self.max_players and len(self.data["players"]) >= self.max_players:
                raise GameError(f"Ten sektor osiągnął ustawiony przez gospodarza limit {self.max_players} kont. Jeśli masz już konto, wybierz Zaloguj.", 409)
            empty = [p for p in self.data["planets"].values() if p["owner_type"] == "empty"]
            if not empty:
                raise GameError("W galaktyce nie ma już wolnej planety startowej.", 409)
            occupied = [p for p in self.data["planets"].values() if p["owner_type"] != "empty"]
            p = max(empty, key=lambda candidate: (min(self._distance(candidate, q) for q in occupied), -candidate["slot"]))
            pid = ident("u")
            player = {"id": pid, "name": name, "race_id": "", "swarm_crystals": 0, "skill_nodes": [], "home_id": p["id"], "protected_until": self.now + 86400, "research": dict.fromkeys(RESEARCH, 0), "reports": [], "requests": {}}
            p["owner_type"], p["owner_id"] = "player", pid
            p["buildings"] = dict.fromkeys(BUILDINGS, 1)
            p["resources"] = {"metal": 4000.0, "crystal": 2600.0, "fuel": 1400.0}
            p["ships"] = {"scout": 2, "cargo": 1, "colonizer": 1, "frigate": 3, "cruiser": 0}
            self.data["players"][pid] = player
            self._report(pid, "Witaj w Alien Colonies", "Wybierz rasę i otwórz koło umiejętności. Wyślij trzy startowe okręty bojowe na słaby przyczółek Roju. Po ich powrocie zdobędziesz Kryształy Roju na pierwszy rozwój. Rozbity przyczółek staje się wolną planetą. Ochrona przed atakami trwa 24 godziny. Zwykłe kryształy służą gospodarce, a Kryształy Roju — wyłącznie umiejętnościom.")
            self.db.execute("INSERT INTO accounts VALUES(?,?,?,?)", (pid, name.casefold(), salt, password_hash))
            token = self._session(pid)
            self._save()
            return {"ok": True, "token": token, "state": self.state(pid), "message": "Założono imperium."}

    def login(self, name, password):
        name, password = self._credentials(name, password)
        with self.lock:
            row = self.db.execute("SELECT id,salt,password_hash FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone()
            salt = row[1] if row else "00" * 16
            candidate = self._password_hash(password, salt)
            if not row or not hmac.compare_digest(candidate, row[2]):
                raise GameError("Nieprawidłowa nazwa lub hasło.", 401)
            token = self._session(row[0])
            self.db.commit()
            return {"ok": True, "token": token, "state": self.state(row[0]), "message": "Witaj ponownie."}

    def authenticate(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise GameError("Zaloguj się ponownie.", 401)
        with self.lock:
            row = self.db.execute("SELECT player_id FROM sessions WHERE token_hash=? AND expires>?", (hashlib.sha256(token.encode()).hexdigest(), self.now)).fetchone()
            if not row:
                raise GameError("Sesja wygasła. Zaloguj się ponownie.", 401)
            return row[0]

    def logout(self, token):
        with self.lock:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
            self.db.commit()

    def _player(self, player_id):
        player = self.data["players"].get(player_id)
        if not player:
            raise GameError("Nie znaleziono gracza.", 401)
        return player

    def _owned(self, player_id, planet_id=None):
        player = self._player(player_id)
        if planet_id is None:
            planet_id = player["home_id"]
        if not isinstance(planet_id, str):
            raise GameError("Nieprawidłowa planeta.")
        p = self.data["planets"].get(planet_id)
        if not p or p["owner_id"] != player_id or p["owner_type"] != "player":
            raise GameError("Ta planeta nie należy do ciebie.", 403)
        return p

    def _report(self, player_id, title, text, art_key="", swarm_crystals=0):
        player = self.data["players"].get(player_id)
        if player:
            player["reports"].insert(0, {"id": ident("r"), "at": self.now, "title": title, "text": text, "art_key": art_key, "swarm_crystals": swarm_crystals})
            del player["reports"][80:]

    def _distance(self, a, b):
        sa = self.data["systems"][int(a["system_id"][1:]) - 1]
        sb = self.data["systems"][int(b["system_id"][1:]) - 1]
        return math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]) + abs(a["slot"] - b["slot"]) * 0.08 + 0.1

    def _flight_numbers(self, origin, target, fleet, propulsion=0):
        distance = self._distance(origin, target)
        specs = self._specs(origin["owner_id"], "ships")
        slowest = min(specs[k][8] for k, n in fleet.items() if n)
        seconds = max(8, math.ceil((100 + distance * 130) / slowest / (1 + propulsion * .15) / self.speed))
        fuel = max(1, math.ceil(sum(specs[k][7] * n for k, n in fleet.items()) * (1 + distance) * 2))
        return seconds, fuel

    def _fleet_quote(self, player_id, payload):
        p = self._owned(player_id, payload.get("planet_id"))
        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or target_id not in self.data["planets"]:
            raise GameError("Wybierz planetę docelową.")
        target = self.data["planets"][target_id]
        if target_id == p["id"]:
            raise GameError("Wybierz inną planetę.")
        mission = payload.get("mission")
        if mission not in ("scout", "transport", "colonize", "attack"):
            raise GameError("Nieznany rodzaj misji.")
        specs = self._specs(player_id, "ships")
        race_id = self._race_id(player_id)
        ships = counts(payload.get("ships"), SHIPS, "Liczba statków", 10_000)
        cargo = counts(payload.get("cargo", {}), RESOURCES, "Ładunek", MAX_RESOURCE)
        if not sum(ships.values()):
            raise GameError("Wybierz przynajmniej jeden statek.")
        if any(n > p["ships"][k] for k, n in ships.items()):
            raise GameError("Nie masz tylu statków na tej planecie.")
        if len([f for f in self.data["fleets"].values() if f["owner_id"] == player_id]) >= 8:
            raise GameError("Możesz prowadzić najwyżej 8 misji naraz.", 409)
        if mission == "scout" and ships["scout"] < 1:
            raise GameError(f"Wymagany okręt do zwiadu: {specs['scout'][0]}." if race_id else "Zwiad wymaga zwiadowcy.")
        if mission == "transport" and target["owner_id"] != player_id:
            raise GameError("Transport jest dostępny między twoimi planetami.")
        if mission == "colonize":
            if ships["colonizer"] < 1 or target["owner_type"] != "empty":
                raise GameError(f"Kolonizacja wymaga okrętu {specs['colonizer'][0]} i wolnej planety." if race_id else "Kolonizacja wymaga kolonizatora i wolnej planety.")
            colonies = sum(q["owner_id"] == player_id for q in self.data["planets"].values())
            pending = sum(f["owner_id"] == player_id and f["mission"] == "colonize" and f["status"] == "outbound" for f in self.data["fleets"].values())
            if colonies + pending >= MAX_COLONIES:
                raise GameError("Limit to 3 kolonie, wliczając wysłane ekspedycje.", 409)
        if mission == "attack":
            if ships["frigate"] + ships["cruiser"] == 0:
                raise GameError(f"Wymagany okręt do ataku: {specs['frigate'][0]} lub {specs['cruiser'][0]}." if race_id else "Atak wymaga fregaty lub krążownika.")
            if target["owner_type"] == "empty" or target["owner_id"] == player_id:
                raise GameError("Możesz atakować obce kolonie lub innych graczy.")
            if target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now:
                raise GameError("Ten gracz jest objęty ochroną startową.", 403)
        if mission not in ("transport", "colonize") and sum(cargo.values()):
            raise GameError("Ładunek można zabrać na transport lub kolonizację.")
        capacity = fleet_capacity(specs, ships)
        if sum(cargo.values()) > capacity:
            raise GameError(f"Ładunek przekracza pojemność {capacity}.")
        seconds, fuel = self._flight_numbers(p, target, ships, self._player(player_id)["research"]["propulsion"])
        cost = dict(cargo)
        cost["fuel"] += fuel
        if not affordable(p, cost):
            raise GameError(f"Brakuje zapasów. Lot wymaga {fuel} paliwa, oprócz zabieranego ładunku.")
        return p, target, ships, cargo, cost, seconds, fuel, capacity

    def preview(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError("Nieprawidłowe dane misji.")
            p, target, ships, cargo, cost, seconds, fuel, capacity = self._fleet_quote(player_id, payload)
            return {"ok": True, "fuel_cost": fuel, "seconds": seconds, "capacity": capacity, "message": "Paliwo obejmuje podróż w obie strony."}

    def _catalog(self, player_id, p):
        player = self._player(player_id)
        result = {"buildings": [], "research": [], "ships": []}
        race_id = self._race_id(player_id)
        rules = self._rules(player_id)
        for group in ("buildings", "research", "ships"):
            for key, spec in self._specs(player_id, group).items():
                level = (p["buildings"] if group == "buildings" else player["research"] if group == "research" else p["ships"])[key]
                cost = scaled_cost(spec[2], level if group != "ships" else 0)
                duration_bonus = self._bonuses(player_id).get("research_speed" if group == "research" else "build_speed", 0)
                seconds = max(1, math.ceil(spec[3] * (1.3 ** level if group != "ships" else 1) / self.speed / (1.0 + duration_bonus)))
                reason = ""
                if p["queue"]:
                    reason = "Planeta realizuje już projekt."
                elif group != "ships" and level >= 12:
                    reason = "Osiągnięto maksymalny poziom 12."
                elif group == "research" and p["buildings"]["lab"] < 1:
                    reason = f"Wymagany budynek: {self._specs(player_id, 'buildings')['lab'][0]}." if race_id else "Wymaga laboratorium."
                elif group == "research" and any(q["queue"] and q["queue"][0]["kind"] == "research" for q in self.data["planets"].values() if q["owner_id"] == player_id):
                    reason = "Badanie trwa na innej planecie."
                elif group == "ships" and p["buildings"]["shipyard"] < (2 if key == "cruiser" else 1):
                    if race_id:
                        reason = f"Wymagany budynek: {self._specs(player_id, 'buildings')['shipyard'][0]} (poziom {2 if key == 'cruiser' else 1})."
                    else:
                        reason = "Wymaga stoczni poziomu 2." if key == "cruiser" else "Wymaga stoczni."
                elif not affordable(p, cost):
                    reason = "Brakuje surowców."
                item = {"key": key, "name": spec[0], "description": spec[1], "level": level, "cost": cost, "seconds": seconds, "enabled": not reason, "reason": reason}
                role = "scout" if key == "propulsion" else "weapon" if key == "weapons" else key
                item["art_key"] = art_key(race_id, role)
                item["race_id"] = race_id
                if group == "ships":
                    item.update(count=level, attack=spec[4], hull=spec[5], capacity=spec[6],
                                fuel=spec[7], speed=spec[8],
                                effective_attack=spec[4] * (1 + player["research"]["weapons"] * .15),
                                effective_speed=spec[8] * (1 + player["research"]["propulsion"] * .15),
                                first_volley_multiplier=rules["first_volley_multiplier"],
                                regeneration_fraction=rules["regeneration_fraction"],
                                damage_reduction=rules["damage_reduction"])
                elif group == "buildings":
                    if key in rules["energy_use_per_level"]:
                        resource, base, rate = {"metal_mine": ("metal", 90, 450),
                                                "crystal_mine": ("crystal", 60, 330),
                                                "refinery": ("fuel", 30, 180)}[key]
                        multiplier = rules["production_multipliers"][resource]
                        item.update(production_resource=resource,
                                    production_per_level=rate * multiplier * self.speed,
                                    base_production=base * multiplier * self.speed,
                                    energy_per_level=rules["energy_use_per_level"][key])
                    elif key == "power_plant":
                        item["energy_supply_per_level"] = rules["energy_supply_per_level"]
                        energy_text = f"{rules['energy_supply_per_level']:g}".replace(".", ",")
                        item["description"] = f"Zapewnia {energy_text} energii na poziom, z uwzględnieniem umiejętności. Energia zasila wydobycie."
                result[group].append(item)
        return result

    def action(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError("Nieprawidłowe polecenie.")
            p = self._owned(player_id, payload.get("planet_id"))
            player = self._player(player_id)
            request_id = payload.get("request_id")
            if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 100):
                raise GameError("Nieprawidłowy identyfikator polecenia.")
            try:
                fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                raise GameError("Polecenie zawiera nieprawidłowe wartości.")
            if request_id in player["requests"]:
                prior = player["requests"][request_id]
                if prior["fingerprint"] != fingerprint:
                    raise GameError("Ten identyfikator został użyty dla innego polecenia.", 409)
                return {"ok": True, "state": self.state(player_id, p["id"]), "message": prior["message"]}
            kind = payload.get("type")
            if kind == "choose_race":
                race_id = payload.get("race_id")
                if not isinstance(race_id, str) or race_id not in RACES:
                    raise GameError("Wybierz jedną z trzech dostępnych ras.")
                reason = self._race_choice_reason(player_id)
                if reason:
                    raise GameError(reason, 409)
                player["race_id"] = race_id
                player["skill_nodes"] = skill_tree.unlocked_for(race_id, [])
                player.setdefault("swarm_crystals", 0)
                message = f"Wybrano rasę: {RACES[race_id]['name']}. To stały wybór tego imperium."
                self._report(player_id, "Narodziny cywilizacji", message + " " + RACES[race_id]["trait"] + " " + RACES[race_id]["tradeoff"])
            elif kind == "unlock_skill":
                try:
                    quote = skill_tree.quote_unlock(self._race_id(player_id), player.get("skill_nodes", []),
                                                    payload.get("node_id"), player.get("swarm_crystals", 0))
                except (ValueError, TypeError) as exc:
                    raise GameError(str(exc), 409) from None
                player["skill_nodes"] = quote["unlocks"]
                player["swarm_crystals"] = quote["balance_after"]
                node = next(node for node in skill_tree.graph()["nodes"] if node["id"] == quote["node_id"])
                message = f"Rozwinięto umiejętność: {node['name']}. Wydano {quote['cost']} Kryształów Roju."
                self._report(player_id, "Nowa umiejętność", message, node.get("art_key", ""))
            elif kind == "fleet":
                p, target, ships, cargo, cost, seconds, fuel, _ = self._fleet_quote(player_id, payload)
                spend(p, cost)
                for key, n in ships.items():
                    p["ships"][key] -= n
                mission = payload["mission"]
                if mission == "attack" and target["owner_type"] == "player":
                    player["protected_until"] = min(player["protected_until"], self.now)
                fleet = {"id": ident("f"), "owner_id": player_id, "race_id": self._race_id(player_id), "origin_id": p["id"], "target_id": target["id"], "mission": mission, "status": "outbound", "ships": ships, "cargo": cargo, "swarm_crystals": 0, "seconds": seconds, "arrives_at": self.now + seconds}
                self.data["fleets"][fleet["id"]] = fleet
                message = f"Flota wyruszyła: {seconds} s, koszt {fuel} paliwa za podróż w obie strony."
            elif kind in ("build", "research", "ship"):
                group = {"build": "buildings", "research": "research", "ship": "ships"}[kind]
                key = payload.get("key")
                entry = next((x for x in self._catalog(player_id, p)[group] if x["key"] == key), None)
                if entry is None:
                    raise GameError("Nieznany projekt.")
                if not entry["enabled"]:
                    raise GameError(entry["reason"], 409)
                amount = integer(payload.get("amount", 1), "Liczba statków", 1, 20) if kind == "ship" else 1
                cost = {k: v * amount for k, v in entry["cost"].items()}
                if not affordable(p, cost):
                    raise GameError("Brakuje surowców na całą partię.", 409)
                spend(p, cost)
                duration = entry["seconds"] * amount
                p["queue"].append({"id": ident("q"), "kind": kind, "key": key, "amount": amount,
                                   "level": entry["level"] + 1, "started_at": self.now,
                                   "seconds": duration, "ends_at": self.now + duration})
                message = "Rozpoczęto projekt."
            else:
                raise GameError("Nieznane polecenie.")
            if request_id:
                player["requests"][request_id] = {"fingerprint": fingerprint, "message": message}
                while len(player["requests"]) > 128:
                    del player["requests"][next(iter(player["requests"]))]
            self._save()
            return {"ok": True, "state": self.state(player_id, p["id"]), "message": message}

    def _return(self, f):
        if sum(f["ships"].values()) == 0:
            self.data["fleets"].pop(f["id"], None)
            return
        f["status"] = "returning"
        origin = self.data["planets"][f["origin_id"]]
        if origin["owner_id"] != f["owner_id"]:
            homes = [p for p in self.data["planets"].values() if p["owner_id"] == f["owner_id"]]
            if not homes:
                self.data["fleets"].pop(f["id"], None)
                return
            target = self.data["planets"][f["target_id"]]
            origin = min(homes, key=lambda p: self._distance(target, p))
            f["origin_id"] = origin["id"]
            f["seconds"], _ = self._flight_numbers(origin, target, f["ships"])
        f["arrives_at"] = self.now + f["seconds"]

    def _land(self, p, f):
        # Settled flights cannot be credited twice, including stale event references.
        if f["id"] not in self.data["fleets"]:
            return False
        # An eradicated outpost cannot hand its returning Swarm ships to a player.
        if p["owner_id"] != f["owner_id"]:
            self._return(f)
            return False
        for key, n in f["ships"].items():
            p["ships"][key] += n
        for k, v in f["cargo"].items():
            p["resources"][k] = min(MAX_RESOURCE, p["resources"][k] + v)
        crystals = int(f.get("swarm_crystals", 0))
        player = self.data["players"].get(f["owner_id"])
        if player and crystals:
            player["swarm_crystals"] = player.get("swarm_crystals", 0) + crystals
        self.data["fleets"].pop(f["id"], None)
        return True

    def _complete_fleet(self, f):
        if f["id"] not in self.data["fleets"]:
            return
        target = self.data["planets"][f["target_id"]]
        owner = f["owner_id"]
        if f["status"] == "returning":
            p = self.data["planets"][f["origin_id"]]
            crystals = int(f.get("swarm_crystals", 0))
            if self._land(p, f):
                reward = f" Przywieziono {crystals} Kryształów Roju — możesz wydać je w kole umiejętności." if crystals else ""
                self._report(owner, "Flota wróciła", f"Statki wróciły na {p['name']}. Ładunek został rozładowany." + reward,
                             "swarm/crystal" if crystals else "", crystals)
            return
        mission = f["mission"]
        if mission == "scout":
            owner_name = "Wolna planeta" if target["owner_type"] == "empty" else self.data["alien"]["name"] if target["owner_type"] == "alien" else self._player(target["owner_id"])["name"]
            stocks = ", ".join(f"{name}: {int(target['resources'][key])}" for key, name in zip(RESOURCES, ("metal", "kryształy", "paliwo")))
            target_specs = self._specs(target["owner_id"], "ships")
            ships = ", ".join(f"{target_specs[k][0]} ×{n}" for k, n in target["ships"].items() if n) or "brak statków"
            detail = ""
            if target["owner_id"] == "khar":
                stage = swarm.public_planet(target)
                structures = ", ".join(f"{swarm.BUILDINGS[key][0]} {level}" for key, level in target["buildings"].items() if level)
                detail = f" {stage['swarm_kind_name']}. Kryształy Roju: {int(target.get('swarm_crystals', 0))}. Budynki Roju: {structures}. Zwycięstwo nad przyczółkiem oczyszcza planetę."
            self._report(owner, "Raport zwiadu", f"{target['name']} — {owner_name}. Zapasy: {stocks}. Flota: {ships}." + detail,
                         "swarm/colony" if target["owner_id"] == "khar" else "")
            self._return(f)
        elif mission == "transport":
            if target["owner_id"] == owner:
                for k, v in f["cargo"].items():
                    target["resources"][k] = min(MAX_RESOURCE, target["resources"][k] + v)
                f["cargo"] = dict.fromkeys(RESOURCES, 0)
                self._report(owner, "Dostarczono transport", f"Zapasy dotarły na {target['name']}. Statki wracają.")
            else:
                self._report(owner, "Transport zawrócił", "Planeta docelowa zmieniła właściciela.")
            self._return(f)
        elif mission == "colonize":
            count = sum(p["owner_id"] == owner for p in self.data["planets"].values())
            limit = swarm.MAX_COLONIES if owner == "khar" else MAX_COLONIES
            if target["owner_type"] == "empty" and count < limit and f["ships"]["colonizer"] > 0:
                target["owner_type"] = "alien" if owner == "khar" else "player"
                target["owner_id"] = owner
                target["buildings"] = dict.fromkeys(BUILDINGS, 0)
                for k in ("metal_mine", "crystal_mine", "refinery", "power_plant"):
                    target["buildings"][k] = 1
                target["resources"] = {"metal": 450.0, "crystal": 250.0, "fuel": 150.0}
                if owner == "khar":
                    # The seed hull pays for the nest. Its escort consists of real ships
                    # removed from the origin, and never appears for free on arrival.
                    target.update(swarm_kind="outpost", swarm_crystals=0.0,
                                  swarm_established_at=self.now, swarm_next_attack_at=self.now + 300,
                                  swarm_suppressed_until=0)
                    target["resources"] = {"metal": 120.0, "crystal": 65.0, "fuel": 35.0}
                    target["buildings"]["shipyard"] = 1
                f["ships"]["colonizer"] -= 1
                self._land(target, f)
                self._report(owner, "Nowa kolonia", f"Założono kolonię {target['name']}. Kolonizator rozebrano na bazę; pozostałe statki i zapasy zostały na miejscu.")
                if owner == "khar":
                    for player_id in self.data["players"]:
                        self._report(player_id, "Rój Khar rozszerza granice", f"Zarodnia dotarła na {target['name']}. Chmara zbudowała przyczółek. Rozbij go, zanim wypuści kolejne zarodnie.", "swarm/colony")
            else:
                self._report(owner, "Kolonizacja przerwana", f"{target['name']} nie jest już dostępna lub osiągnięto limit kolonii. Flota wraca.")
                self._return(f)
        else:
            if target["owner_type"] == "empty" or target["owner_id"] == owner or (target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now):
                self._report(owner, "Atak odwołany", "Cel nie może zostać zaatakowany. Flota wraca.")
                self._return(f)
            else:
                self._battle(f, target)

    @staticmethod
    def _power(fleet, weapons, specs=None, multiplier=1.0):
        specs = SHIPS if specs is None else specs
        return sum(specs[k][4] * n for k, n in fleet.items()) * (1 + weapons * .15) * multiplier

    @staticmethod
    def _damage(fleet, damage, wounds, specs=None, damage_reduction=0.0):
        # Small ships absorb damage first; surviving wounds persist between rounds.
        specs = SHIPS if specs is None else specs
        damage *= 1.0 - damage_reduction
        for key in sorted(specs, key=lambda k: (specs[k][5], k)):
            if fleet[key] <= 0:
                continue
            hull = specs[key][5]
            remaining = fleet[key] * hull - wounds.get(key, 0)
            hit = min(damage, remaining)
            total = wounds.get(key, 0) + hit
            killed = min(fleet[key], int(total // hull))
            fleet[key] -= killed
            wounds[key] = total - killed * hull if fleet[key] else 0
            damage -= hit
            if damage <= 0:
                break

    @staticmethod
    def _regenerate(fleet, wounds, fraction):
        # Heal only the partially wounded surviving ship, never resurrect losses.
        for key in wounds:
            wounds[key] = wounds[key] * (1.0 - fraction) if fleet[key] > 0 else 0

    def _battle(self, f, target):
        attacking_before = dict(f["ships"])
        defending_before = dict(target["ships"])
        attacker = f["owner_id"]
        defender = target["owner_id"]
        aw = 0 if attacker == "khar" else self._player(attacker)["research"]["weapons"]
        dw = 0 if defender == "khar" else self._player(defender)["research"]["weapons"]
        specs_a, specs_d = self._specs(attacker, "ships"), self._specs(defender, "ships")
        rules_a, rules_d = self._rules(attacker), self._rules(defender)
        wounds_a, wounds_d = {}, {}
        anti_swarm_a = 1.0 + (self._bonuses(attacker).get("swarm_damage", 0) if defender == "khar" else 0)
        anti_swarm_d = 1.0 + (self._bonuses(defender).get("swarm_damage", 0) if attacker == "khar" else 0)
        rounds = 0
        for _ in range(6):
            if not sum(f["ships"].values()) or not sum(target["ships"].values()):
                break
            rounds += 1
            attack = self._power(f["ships"], aw, specs_a, (rules_a["first_volley_multiplier"] if rounds == 1 else 1.0) * anti_swarm_a)
            defense = self._power(target["ships"], dw, specs_d, (rules_d["first_volley_multiplier"] if rounds == 1 else 1.0) * anti_swarm_d)
            self._damage(target["ships"], attack, wounds_d, specs_d, rules_d["damage_reduction"])
            self._damage(f["ships"], defense, wounds_a, specs_a, rules_a["damage_reduction"])
            self._regenerate(f["ships"], wounds_a, rules_a["regeneration_fraction"])
            self._regenerate(target["ships"], wounds_d, rules_d["regeneration_fraction"])
        victory = sum(target["ships"].values()) == 0 and sum(f["ships"].values()) > 0
        capacity = fleet_capacity(specs_a, f["ships"])
        f["cargo"] = dict.fromkeys(RESOURCES, 0)
        f["swarm_crystals"] = 0
        eradicated = False
        if victory:
            if defender == "khar" and attacker in self.data["players"]:
                stage = swarm.kind(target)
                quota = math.floor(swarm.RAID_CRYSTALS[stage] * (1.0 + self._bonuses(attacker).get("swarm_loot", 0)))
                crystals = min(int(target.get("swarm_crystals", 0)), quota, capacity)
                target["swarm_crystals"] = max(0.0, target.get("swarm_crystals", 0) - crystals)
                f["swarm_crystals"] = crystals
                capacity -= crystals
                eradicated = stage == "outpost"
                target["swarm_suppressed_until"] = self.now + max(120, 1200 / self.speed)
                if stage == "hive":
                    target["buildings"]["shipyard"] = max(0, target["buildings"]["shipyard"] - 1)
                    target["queue"] = []
            available = {k: int(v * .35) for k, v in target["resources"].items()}
            total = sum(available.values())
            if total:
                for k, v in available.items():
                    n = min(v, math.floor(capacity * v / total)) if total > capacity else v
                    f["cargo"][k] = n
                    target["resources"][k] -= n
        if eradicated:
            target.update(owner_id="", owner_type="empty", resources=dict.fromkeys(RESOURCES, 0.0),
                          buildings=dict.fromkeys(BUILDINGS, 0), ships=blank_ships(), queue=[])
            for key in tuple(target):
                if key.startswith("swarm_"):
                    del target[key]
        lost_a = ", ".join(f"{specs_a[k][0]} ×{n-f['ships'][k]}" for k, n in attacking_before.items() if n > f["ships"][k]) or "brak"
        lost_d = ", ".join(f"{specs_d[k][0]} ×{n-target['ships'][k]}" for k, n in defending_before.items() if n > target["ships"][k]) or "brak"
        outcome = "Zwycięstwo" if victory else "Klęska" if sum(f["ships"].values()) == 0 else "Nierozstrzygnięta bitwa — odwrót"
        summary = f"{target['name']}: {outcome}. Rundy: {rounds}. Straty atakującego: {lost_a}. Straty obrońcy: {lost_d}. Zdobycz: metal {f['cargo']['metal']}, kryształy {f['cargo']['crystal']}, paliwo {f['cargo']['fuel']}. "
        if defender == "khar":
            summary += f" Kryształy Roju: {f['swarm_crystals']} w ładowni; trafią do koła po powrocie floty."
            if eradicated:
                summary += " Przyczółek został zniszczony. Planeta jest wolna i można ją skolonizować."
            elif victory:
                summary += " Wylęgarnia ula straciła poziom, a jego ekspansja została czasowo zatrzymana."
        else:
            summary += " Budynki i własność planety pozostają bez zmian."
        for label, owner_id in (("Atakujący", attacker), ("Obrońca", defender)):
            race_id = self._race_id(owner_id)
            if race_id:
                rules = self._rules(owner_id)
                effects = []
                if rules["first_volley_multiplier"] > 1:
                    effects.append(f"pierwsza salwa +{round((rules['first_volley_multiplier'] - 1) * 100)}%")
                if rules["regeneration_fraction"]:
                    effects.append(f"regeneracja {round(rules['regeneration_fraction'] * 100)}% ran po rundzie")
                if rules["damage_reduction"]:
                    effects.append(f"redukcja obrażeń {round(rules['damage_reduction'] * 100)}%")
                summary += f" {label} — {RACES[race_id]['name']}: {RACES[race_id]['weapon_name']}; {', '.join(effects)}."
        self._report(attacker, "Raport bitwy", summary, "swarm/weapon" if defender == "khar" else "", f["swarm_crystals"])
        self._report(defender, "Twoja kolonia została zaatakowana", summary, "swarm/weapon" if attacker == "khar" else "")
        self._return(f)

    def _swarm_launch(self, origin, target, mission, ships):
        seconds, fuel = self._flight_numbers(origin, target, ships)
        if origin["resources"]["fuel"] < fuel or any(n > origin["ships"][k] for k, n in ships.items()):
            return None
        origin["resources"]["fuel"] -= fuel
        for key, n in ships.items():
            origin["ships"][key] -= n
        f = {"id": ident("f"), "owner_id": "khar", "race_id": "swarm", "origin_id": origin["id"],
             "target_id": target["id"], "mission": mission, "status": "outbound", "ships": ships,
             "cargo": dict.fromkeys(RESOURCES, 0), "swarm_crystals": 0,
             "seconds": seconds, "arrives_at": self.now + seconds}
        self.data["fleets"][f["id"]] = f
        return f

    def _swarm_queue(self, p, kind, key, amount=1):
        if p["queue"]:
            return False
        if kind == "ship" and p["buildings"]["shipyard"] < (2 if key == "cruiser" else 1):
            kind, key, amount = "build", "shipyard", 1
        spec = self._specs("khar", "ships" if kind == "ship" else "buildings")[key]
        level = 0 if kind == "ship" else p["buildings"][key]
        if level >= 8:
            return False
        cost = {k: v * amount for k, v in scaled_cost(spec[2], level).items()}
        if not affordable(p, cost):
            return False
        spend(p, cost)
        duration = max(1, math.ceil(spec[3] * 1.3 ** level * amount / self.speed))
        p["queue"].append({"id": ident("q"), "kind": kind, "key": key, "amount": amount,
                           "level": level + 1, "started_at": self.now, "seconds": duration,
                           "ends_at": self.now + duration})
        return True

    def _alien_turn(self):
        colonies = [p for p in self.data["planets"].values() if p["owner_id"] == "khar"]
        pending = [f for f in self.data["fleets"].values() if f["owner_id"] == "khar" and f["mission"] == "colonize" and f["status"] == "outbound"]
        # A single bounded decision per world, never replayed for offline time.
        for p in colonies:
            if p["queue"] or p.get("swarm_suppressed_until", 0) > self.now:
                continue
            hive = swarm.kind(p) == "hive"
            defense_cap = 36 if hive else 6
            mature = hive or self.now - p.get("swarm_established_at", self.now) >= 120
            if hive and p["ships"]["frigate"] >= 24 and p.get("swarm_next_attack_at", 0) <= self.now:
                already_targeted = {f["target_id"] for f in self.data["fleets"].values()
                                    if f["owner_id"] == "khar" and f["mission"] == "attack" and f["status"] == "outbound"}
                targets = [q for q in self.data["planets"].values() if q["owner_type"] == "player"
                           and self._player(q["owner_id"])["protected_until"] <= self.now
                           and q["id"] not in already_targeted]
                if targets:
                    target = min(targets, key=lambda q: (self._distance(p, q), q["id"]))
                    ships = blank_ships()
                    ships["frigate"] = 12
                    f = self._swarm_launch(p, target, "attack", ships)
                    if f:
                        p["swarm_next_attack_at"] = self.now + max(90, 900 / self.speed)
                        self._report(target["owner_id"], "Nadciąga chmara Roju", f"12 żuwaczy wyruszyło z {p['name']} na {target['name']}. Przybędą za {f['seconds']} s.", "swarm/weapon")
                        continue
            if p["ships"]["frigate"] < (12 if hive else 4):
                self._swarm_queue(p, "ship", "frigate", min(3 if hive else 2, defense_cap - p["ships"]["frigate"]))
                continue
            can_expand = mature and len(colonies) + len(pending) < swarm.MAX_COLONIES
            if can_expand and p["ships"]["colonizer"] and p["ships"]["frigate"] >= 6:
                reserved = {f["target_id"] for f in pending}
                empty = [q for q in self.data["planets"].values() if q["owner_type"] == "empty" and q["id"] not in reserved]
                if empty:
                    target = min(empty, key=lambda q: (self._distance(p, q), q["id"]))
                    ships = blank_ships()
                    ships["colonizer"], ships["frigate"] = 1, 2
                    f = self._swarm_launch(p, target, "colonize", ships)
                    if f:
                        pending.append(f)
                        for player_id in self.data["players"]:
                            self._report(player_id, "Wykryto zarodnię Roju", f"Zarodnia z eskortą dwóch żuwaczy leci z {p['name']} na {target['name']}. Do celu: {f['seconds']} s.", "swarm/colonizer")
                        continue
            if can_expand and not p["ships"]["colonizer"]:
                if self._swarm_queue(p, "ship", "colonizer"):
                    continue
            if p["ships"]["frigate"] < defense_cap:
                if self._swarm_queue(p, "ship", "frigate", min(3 if hive else 2, defense_cap - p["ships"]["frigate"])):
                    continue
            if hive and p["ships"]["cruiser"] < 2 and p["ships"]["frigate"] >= 30:
                if self._swarm_queue(p, "ship", "cruiser"):
                    continue
            key = "power_plant" if self.energy(p)["factor"] < 1.0 else min(("metal_mine", "crystal_mine", "refinery"), key=lambda k: p["buildings"][k])
            self._swarm_queue(p, "build", key)

    def state(self, player_id, planet_id=None):
        with self.lock:
            player = self._player(player_id)
            p = self._owned(player_id, planet_id)
            galaxy = []
            own = []
            for system in self.data["systems"]:
                view = {k: system[k] for k in ("id", "name", "x", "y")}
                view["planets"] = []
                for pid in system["planet_ids"]:
                    q = self.data["planets"][pid]
                    item = {k: q[k] for k in ("id", "name", "system_id", "slot", "owner_type", "owner_id")}
                    item["owner_name"] = "" if q["owner_type"] == "empty" else self.data["alien"]["name"] if q["owner_type"] == "alien" else self._player(q["owner_id"])["name"]
                    if q["owner_type"] == "player":
                        item["protected_until"] = self._player(q["owner_id"])["protected_until"]
                    race_id = self._race_id(q["owner_id"])
                    item.update(race_id=race_id, race_name=RACES[race_id]["name"] if race_id else "",
                                colony_art=art_key(race_id, "colony"))
                    if q["owner_id"] == "khar":
                        item.update(swarm.public_planet(q))
                    view["planets"].append(item)
                    if q["owner_id"] == player_id:
                        own.append({k: item[k] for k in ("id", "name", "system_id", "race_id", "race_name", "colony_art")})
                galaxy.append(view)
            fleets = []
            alien_fleets = []
            for f in self.data["fleets"].values():
                if f["owner_id"] != player_id and f["owner_id"] != "khar":
                    continue
                view = {k: copy.deepcopy(f[k]) for k in ("id", "origin_id", "target_id", "mission", "status", "ships", "arrives_at")}
                view["origin_name"] = self.data["planets"][f["origin_id"]]["name"]
                view["target_name"] = self.data["planets"][f["target_id"]]["name"]
                race_id = self._race_id(f["owner_id"])
                view.update(race_id=race_id, race_name=RACES[race_id]["name"] if race_id else "",
                            seconds=f.get("seconds", 0), cargo=copy.deepcopy(f.get("cargo", {})),
                            swarm_crystals=int(f.get("swarm_crystals", 0)))
                if f["owner_id"] == "khar":
                    role = "colonizer" if f["mission"] == "colonize" else "frigate"
                    view.update(race_id="swarm", race_name="Rój Khar", art_key="swarm/" + role,
                                ship_names={key: swarm.SHIPS[key][0] for key, count in f["ships"].items() if count})
                (fleets if f["owner_id"] == player_id else alien_fleets).append(view)
            result = {"version": VERSION, "server_time": self.now, "speed": self.speed, "player": {k: player[k] for k in ("id", "name", "protected_until")}, "home_id": player["home_id"], "planet_id": p["id"], "planet_name": p["name"], "resources": {k: int(v) for k, v in p["resources"].items()}, "production": self.production(p), "energy": self.energy(p), "buildings": dict(p["buildings"]), "research": dict(player["research"]), "ships": dict(p["ships"]), "queue": copy.deepcopy(p["queue"]), "catalog": self._catalog(player_id, p), "own_planets": own, "galaxy": galaxy, "fleets": fleets, "reports": copy.deepcopy(player["reports"]), "alien": {**self.data["alien"], "colonies_count": sum(q["owner_id"] == "khar" for q in self.data["planets"].values()), "fleets": alien_fleets}, "limits": {"colonies": MAX_COLONIES}}
            race_id = self._race_id(player_id)
            result["player"].update(race_id=race_id, race_name=RACES[race_id]["name"] if race_id else "",
                                    swarm_crystals=int(player.get("swarm_crystals", 0)))
            result["skill_tree"] = skill_tree.public_state(race_id, player.get("skill_nodes", []), player.get("swarm_crystals", 0))
            weak = [q for q in self.data["planets"].values() if q["owner_id"] == "khar" and swarm.kind(q) == "outpost"]
            recommended = min(weak, key=lambda q: (int(q.get("swarm_crystals", 0)) < 6,
                                                   sum(swarm.SHIPS[key][4] * n for key, n in q["ships"].items()) > 48,
                                                   self._distance(p, q), q["id"])) if weak else None
            result["alien"].update(portrait_art="swarm/portrait", colony_art="swarm/colony", weapon_art="swarm/weapon",
                                   crystal_art="swarm/crystal", description=swarm.DESCRIPTION,
                                   max_colonies=swarm.MAX_COLONIES,
                                   recommended_target_id=recommended["id"] if recommended else "")
            result["races"] = [public_race(key) for key in RACES]
            result["race"] = public_race(race_id) if race_id else {}
            result["race_choice_reason"] = self._race_choice_reason(player_id)
            result["race_choice_allowed"] = not result["race_choice_reason"]
            result["colony_art"] = art_key(race_id, "colony")
            return result


class GameHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, world, trust_proxy_header=None, update_policy=None):
        if trust_proxy_header not in (None, "X-Real-IP"):
            raise ValueError("Only an explicit X-Real-IP proxy header is supported")
        self.world = world
        self.trust_proxy_header = trust_proxy_header
        if update_policy is not None and not isinstance(update_policy, UpdatePolicy):
            raise ValueError("update_policy must be an UpdatePolicy")
        self.update_policy = UpdatePolicy() if update_policy is None else update_policy
        self.rate_lock = threading.Lock()
        self.attempts = defaultdict(deque)
        super().__init__(address, Handler)

    def rate_limit(self, identity, auth=False):
        now = time.monotonic()
        key = (identity, auth)
        with self.rate_lock:
            if len(self.attempts) > 5000:
                self.attempts = defaultdict(deque, {k: v for k, v in self.attempts.items() if v and v[-1] > now - 60})
            attempts = self.attempts[key]
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= (12 if auth else 180):
                raise GameError("Zbyt wiele prób. Spróbuj ponownie za minutę.", 429)
            attempts.append(now)


class Handler(BaseHTTPRequestHandler):
    server_version = "Pogranicze/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Do not log Authorization, credentials, bodies or full query strings.
        pass

    def _json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise GameError("Niedozwolony sposób przesyłania danych.", 400)
        raw_length = self.headers.get("Content-Length", "0")
        if not re.fullmatch(r"[0-9]{1,8}", raw_length):
            raise GameError("Nieprawidłowy rozmiar żądania.")
        length = int(raw_length)
        if length > MAX_BODY:
            raise GameError("Żądanie jest zbyt duże.", 413)
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise GameError("Wymagane dane JSON.", 415)
        try:
            def reject_constant(value):
                raise ValueError(value)
            data = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            # JSON's numeric exponent syntax can overflow a float without using
            # the non-standard NaN/Infinity tokens handled above.
            json.dumps(data, allow_nan=False)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise GameError("Nieprawidłowe dane JSON.")
        if not isinstance(data, dict):
            raise GameError("Żądanie musi być obiektem JSON.")
        return data

    def _client_ip(self):
        # Enable only behind Railway's HTTP ingress. A header is not itself proof
        # of proxy identity: the origin must not also accept untrusted direct
        # traffic. Standalone servers ignore all forwarded headers by default.
        header = self.server.trust_proxy_header
        if header is not None:
            values = self.headers.get_all(header, [])
            if len(values) == 1:
                value = values[0].strip()
                if len(value) <= 45 and "%" not in value:
                    try:
                        return str(ipaddress.ip_address(value))
                    except ValueError:
                        pass
        return self.client_address[0]

    def _handle(self):
        path = urlsplit(self.path)
        world = self.server.world
        if self.command == "GET" and path.path == "/health":
            return {"ok": True, "version": VERSION}
        if self.command == "GET" and path.path == "/api/client-version":
            return self.server.update_policy.manifest()
        client_identity = ("ip", self._client_ip())
        if path.path.startswith("/api/"):
            # Compatibility signal only: authentication remains mandatory for
            # gameplay. Missing, duplicate and malformed headers mean an old APK.
            values = self.headers.get_all("X-PGR-Client-Version", [])
            version = 0
            if len(values) == 1 and re.fullmatch(r"[0-9]{1,10}", values[0]):
                candidate = int(values[0])
                if candidate <= MAX_VERSION_CODE:
                    version = candidate
            if version < self.server.update_policy.min_version_code:
                self.server.rate_limit(client_identity)
                # Stop before credentials, request bodies or game state are read.
                raise UpdateRequired(self.server.update_policy)
        if self.command not in ("GET", "POST"):
            self.server.rate_limit(client_identity)
            raise GameError("Niedozwolona metoda.", 405)
        auth_path = self.command == "POST" and path.path in ("/api/login", "/api/register")
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if auth_path:
            self.server.rate_limit(client_identity, auth=True)
        else:
            try:
                player_id = world.authenticate(token)
            except GameError:
                self.server.rate_limit(client_identity)
                raise
            # Verified accounts have separate quotas even when sharing a mobile
            # carrier NAT, household router, or Railway proxy address. Additional
            # session tokens cannot multiply an account's quota.
            self.server.rate_limit(("player", player_id))
        body = self._body() if self.command == "POST" else None
        with world.lock:
            world.advance()
            if self.command == "POST" and path.path == "/api/register":
                return world.register(body.get("name"), body.get("password"), body.get("invite", ""))
            if self.command == "POST" and path.path == "/api/login":
                return world.login(body.get("name"), body.get("password"))
            # Recheck after advancing time and reading the body: the session may
            # have expired or been revoked by another request in the meantime.
            player_id = world.authenticate(token)
            if self.command == "GET" and path.path == "/api/state":
                planet_id = parse_qs(path.query).get("planet_id", [None])[0]
                return {"ok": True, "state": world.state(player_id, planet_id), "message": ""}
            if self.command == "POST" and path.path == "/api/action":
                return world.action(player_id, body)
            if self.command == "POST" and path.path == "/api/preview":
                return world.preview(player_id, body)
            if self.command == "POST" and path.path == "/api/logout":
                state = world.state(player_id)
                world.logout(token)
                return {"ok": True, "state": state, "message": "Wylogowano."}
            raise GameError("Nie znaleziono adresu API.", 404)

    def _serve(self):
        try:
            self._json(200, self._handle())
        except UpdateRequired as exc:
            self._json(426, {"ok": False, "code": "update_required", "error": exc.message,
                             "update": exc.update})
        except GameError as exc:
            self._json(exc.status, {"ok": False, "error": exc.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as exc:
            # Type only; never print a request, credentials, token or world snapshot.
            print(f"Błąd obsługi żądania: {type(exc).__name__}", flush=True)
            self._json(500, {"ok": False, "error": "Błąd serwera. Spróbuj ponownie."})

    do_GET = _serve
    do_POST = _serve
    do_PUT = _serve
    do_DELETE = _serve


def build_server(world, host="127.0.0.1", port=8765, trust_proxy_header=None, update_policy=None):
    return GameHTTPServer((host, port), world, trust_proxy_header=trust_proxy_header,
                          update_policy=update_policy)


def main(argv=None, trust_proxy_header=None):
    parser = argparse.ArgumentParser(description="Pogranicze Galaktyki — serwer testu multiplayer")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="galaxy.sqlite3")
    parser.add_argument("--speed", type=float, default=10)
    parser.add_argument("--max-players", type=int, default=0,
                        help="Opcjonalny limit kont; 0 (domyślnie) wyłącza limit. Nadal potrzebne są wolne planety.")
    args = parser.parse_args(argv)
    if args.max_players < 0:
        parser.error("--max-players musi być nieujemną liczbą całkowitą")
    update_policy = load_update_policy()
    world = World(args.db, args.speed, max_players=args.max_players)
    server = build_server(world, args.host, args.port, trust_proxy_header=trust_proxy_header,
                          update_policy=update_policy)
    stop = threading.Event()

    def tick():
        while not stop.wait(1):
            try:
                world.advance()
            except Exception as exc:
                print(f"Błąd aktualizacji świata: {type(exc).__name__}", flush=True)

    worker = threading.Thread(target=tick, name="galaxy-tick", daemon=True)
    worker.start()

    def shutdown(signum, frame):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print(f"Pogranicze {VERSION}: http://{args.host}:{args.port}, tempo ×{args.speed:g}", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        stop.set()
        worker.join(timeout=3)
        server.server_close()
        world.close()


if __name__ == "__main__":
    main()
