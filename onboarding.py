"""Five persistent first steps, derived only from authoritative game events.

The guide never grants resources, changes research/ships, or sends a mission.
Call ``record`` within the same transaction as the completed action and include
``public_state`` in the normal state response. Saved markers are monotonic;
only three verifiable facts may be inferred for saves made before this guide.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t

import math

try:
    from . import skill_tree, swarm
    from .galaxies import separation
except ImportError:  # Railway's flat deployment.
    import skill_tree, swarm
    from galaxies import separation


VERSION = 2
BASIC_BUILDINGS = frozenset(("metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab"))
STEPS = (
    ("first_building", "Rozwiń kolonię", "Ukończ ulepszenie jednego z podstawowych budynków.", "building"),
    ("second_colony", "Załóż drugą kolonię", "Wyślij kolonizator na wolną planetę i poczekaj na założenie kolonii.", "colonize"),
    ("swarm_scout", "Poznaj Rój", "Wyślij zwiadowcę do Roju i odczytaj raport o jego obronie.", "scout"),
    ("swarm_crystals", "Zdobądź Kryształy Roju", "Przygotuj silną flotę, przełam obronę gniazda i przywieź rzadkie kryształy. Skoordynuj naloty z innymi graczami.", "hunt"),
    ("first_skill", "Rozwiń swoją rasę", "Kup pierwszą umiejętność. Każdy zakup podnosi koszt pozostałych węzłów.", "skills"),
)
STEP_IDS = frozenset(step[0] for step in STEPS)


def _chosen(player):
    return player.get("race_id") in skill_tree.ROOTS


def _markers(player):
    previous = player.get("onboarding", {})
    previous = previous if isinstance(previous, dict) else {}
    raw = previous.get("completed", {})
    raw = raw if isinstance(raw, dict) else {}
    complete = {key: True for key in STEP_IDS if raw.get(key) is True}
    player["onboarding"] = {"version": VERSION, "completed": complete}
    return complete


def record(player, event):
    """Mark an already completed server event once; return whether data changed.

    ``race_chosen`` initializes metadata without completing a step. Unknown
    events and events before race selection have no effect. This function is
    intentionally not exposed as a client command.
    """
    if not isinstance(player, dict) or not _chosen(player):
        return False
    if event != "race_chosen" and event not in STEP_IDS:
        return False
    before = player.get("onboarding")
    complete = _markers(player)
    if event in STEP_IDS:
        complete[event] = True
    return player["onboarding"] != before


def ensure(data, player):
    """Infer only owned upgrades, a paid non-root node and a second colony.

    Scout reports may have been trimmed and a crystal balance does not prove a
    completed return, so those two events are never reconstructed from guesses.
    Existing true markers survive loss of a colony, spending, or later changes.
    """
    if not _chosen(player):
        return
    complete = _markers(player)
    owned = _owned(data, player)
    if any(type(p.get("buildings", {}).get(key)) is int and p["buildings"][key] >= 2
           for p in owned for key in BASIC_BUILDINGS):
        complete["first_building"] = True
    if len(owned) >= 2:
        complete["second_colony"] = True
    unlocked = set(skill_tree.unlocked_for(player["race_id"], player.get("skill_nodes", [])))
    if any(node["id"] in unlocked and node["id"] not in skill_tree.ROOTS.values()
           and node["cost"] > 0 for node in skill_tree.graph()["nodes"]):
        complete["first_skill"] = True


def _owned(data, player):
    return [p for p in data.get("planets", {}).values()
            if p.get("owner_type") == "player" and p.get("owner_id") == player.get("id")]


def _is_swarm(planet):
    return planet.get("owner_type") == "alien" and planet.get("owner_id") == swarm.OWNER_ID


def _weak_hunt(planet):
    # Historical helper name retained for callers; no weak NPC target is implied.
    return _is_swarm(planet) and int(planet.get("swarm_crystals", 0)) > 0


def _distance(data, origin, target):
    if not origin:
        return 0.0
    systems = {s["id"]: s for s in data.get("systems", [])}
    a, b = systems.get(origin.get("system_id"), {}), systems.get(target.get("system_id"), {})
    return (separation(a.get("galaxy_id", "g1"), b.get("galaxy_id", "g1")) * 1_000_000
            + math.hypot(a.get("x", 0) - b.get("x", 0), a.get("y", 0) - b.get("y", 0))
            + abs(origin.get("slot", 0) - target.get("slot", 0)) * .08)


def public_state(data, player, recommended_target_id="", planet_id=None):
    """Return versioned UI data; all target IDs are rechecked against live owners.

    ``target_id`` is a building key for building, a planet ID for scout/hunt/
    colonize, and empty for the skill wheel. A mission action with an empty
    target must not open/send a
    mission: its description explains waiting for a fleet or a suitable target.
    Supplying a recommendation cannot authorize an attack on a former NPC.
    """
    ensure(data, player)
    chosen = _chosen(player)
    complete = player.get("onboarding", {}).get("completed", {}) if chosen else {}
    planets = data.get("planets", {})
    owned = _owned(data, player)
    origin = next((p for p in owned if p["id"] == planet_id), None)
    origin = origin or next((p for p in owned if p["id"] == player.get("home_id")), None)
    origin = origin or (owned[0] if owned else None)
    fleets = [f for f in data.get("fleets", {}).values() if f.get("owner_id") == player.get("id")]
    weak = [p for p in planets.values() if _weak_hunt(p)]
    preferred = planets.get(recommended_target_id, {})
    hunt = preferred if _weak_hunt(preferred) else min(weak, key=lambda p: (
        int(p.get("swarm_crystals", 0)) < 1, _distance(data, origin, p), p["id"]), default=None)
    swarms = [p for p in planets.values() if _is_swarm(p)]
    scout = hunt or min(swarms, key=lambda p: (swarm.kind(p) == "hive", _distance(data, origin, p), p["id"]), default=None)
    empty = [p for p in planets.values() if p.get("owner_type") == "empty" and not p.get("owner_id")]
    colony = min(empty, key=lambda p: (_distance(data, origin, p), p["id"]), default=None)
    targets = {"building": "metal_mine" if origin else "", "scout": scout["id"] if scout else "",
               "hunt": hunt["id"] if hunt else "", "skills": "",
               "colonize": colony["id"] if colony else ""}
    steps = []
    for ident, title, description, action in STEPS:
        done = complete.get(ident) is True
        target_id = targets[action] if chosen else ""
        if chosen and not done:
            if action == "scout":
                underway = any(f.get("mission") == "scout" and f.get("status") == "outbound"
                               and _is_swarm(planets.get(f.get("target_id"), {})) for f in fleets)
                if underway:
                    target_id, description = "", t('Zwiadowca leci do Roju. Poczekaj na raport z celu.')
                elif not target_id:
                    description = t('Nie ma teraz planety Roju do zbadania. Wróć po zmianie sytuacji w galaktyce.')
            elif action == "hunt":
                returning = any(f.get("status") == "returning" and int(f.get("swarm_crystals", 0)) > 0 for f in fleets)
                if returning:
                    target_id, description = "", t('Flota wraca z Kryształami Roju. Cel zaliczy się po rozładunku we własnej kolonii.')
                elif not target_id:
                    description = t('Gniazda nie mają teraz kryształów. Odnowa: 1 sztuka na 18 godzin po odbudowie obrony. Rozwijaj flotę.')
            elif action == "colonize":
                pending = any(f.get("mission") == "colonize" and f.get("status") == "outbound" for f in fleets)
                if pending:
                    target_id, description = "", t('Kolonizator jest w drodze. Poczekaj na wynik kolonizacji.')
                elif not target_id:
                    description = t('Nie ma teraz wolnej planety. Rozejrzyj się po galaktyce po zmianie sytuacji.')
        steps.append({"id": ident, "title": t(title), "description": t(description), "done": done,
                      "action": action, "target_id": target_id})
    count = sum(step["done"] for step in steps)
    return {"version": VERSION, "completed_count": count, "total": len(STEPS),
            "finished": count == len(STEPS), "steps": steps,
            "current": next((dict(step) for step in steps if not step["done"]), None) if chosen else None}
