"""Authoritative, connected 60-node skill wheel for Alien Colonies.

All bonuses are additive *fractions*, not percentages or multipliers. For example,
``attack: .05`` means multiply ordinary attack by ``1 + .05``. ``first_volley``
uses the same convention. ``regeneration`` and ``damage_reduction`` are direct
fractions. Speed bonuses divide construction/research duration by ``1 + bonus``;
fuel efficiency multiplies fuel cost by ``1 - bonus``. Callers replace legacy
racial combat traits with the three signature-root effects returned here.

The module never mutates a player or spends money. ``quote_unlock`` validates the
whole purchase and returns the replacement unlock list and resulting balance;
the caller commits both within its normal world lock/idempotent action handling.
"""
from __future__ import annotations

import copy
import math
from functools import lru_cache


ROOTS = {race: race + "_root" for race in ("zetans", "automatons", "symbionts")}
EMPTY_RADIUS = 300
BONUS_CAPS = {
    "first_volley": .50, "regeneration": .50, "damage_reduction": .30,
    "production_metal": .60, "production_crystal": .60, "production_fuel": .60,
    "energy": .60, "build_speed": .50, "research_speed": .50,
    "attack": .50, "hull": .60, "flight_speed": .60,
    "fuel_efficiency": .40, "capacity": .60, "swarm_damage": .60,
    "swarm_loot": .50,
}
EFFECT_LABELS = {
    "first_volley": "Siła pierwszej salwy",
    "regeneration": "Leczenie ran ocalałych kadłubów po rundzie",
    "damage_reduction": "Redukcja otrzymanych obrażeń",
    "production_metal": "Produkcja metalu",
    "production_crystal": "Produkcja zwykłych kryształów",
    "production_fuel": "Produkcja paliwa",
    "energy": "Wytwarzana energia", "build_speed": "Tempo budowy i produkcji okrętów",
    "research_speed": "Tempo badań", "attack": "Siła ataku", "hull": "Wytrzymałość kadłubów",
    "flight_speed": "Prędkość lotu", "fuel_efficiency": "Oszczędność paliwa",
    "capacity": "Ładowność", "swarm_damage": "Obrażenia przeciw Rojowi",
    "swarm_loot": "Limit Kryształów Roju zabieranych z celu",
}
SECTORS = [
    {"race_id": "zetans", "name": "Zetanie", "color": "#58baff", "angle": -90},
    {"race_id": "automatons", "name": "Automatony", "color": "#ff655d", "angle": 30},
    {"race_id": "symbionts", "name": "Symbionci", "color": "#69e87f", "angle": 150},
]

# Each race has three four-step branches. Every skill has a separate art motif.
BRANCHES = {
    "zetans": [
        [
            ("Pamięć kryształu", "crystal_memory", {"production_crystal": .08}),
            ("Splot myśli", "thought_lattice", {"research_speed": .08}),
            ("Srebrny rezonans", "silver_resonance", {"production_crystal": .12}),
            ("Wszechwidzące oko", "omniscient_eye", {"research_speed": .14, "energy": .08}),
        ],
        [
            ("Krzywizna przestrzeni", "space_curvature", {"flight_speed": .06}),
            ("Cichy impuls", "silent_impulse", {"fuel_efficiency": .08}),
            ("Kieszeń wymiarowa", "dimension_pocket", {"capacity": .10}),
            ("Wrota grawitacyjne", "gravity_gate", {"flight_speed": .10, "fuel_efficiency": .05}),
        ],
        [
            ("Ostrze fazowe", "phase_blade", {"attack": .05}),
            ("Rozpoznanie słabości", "weakness_scan", {"swarm_damage": .08}),
            ("Błękitna osobliwość", "blue_singularity", {"energy": .10}),
            ("Pryzmat Roju", "swarm_prism", {"swarm_loot": .15, "swarm_damage": .06}),
        ],
    ],
    "automatons": [
        [
            ("Wiertło tytanowe", "titanium_drill", {"production_metal": .08}),
            ("Linia autonomiczna", "assembly_line", {"build_speed": .08}),
            ("Piec plazmowy", "plasma_furnace", {"production_metal": .12}),
            ("Fabryka bez końca", "endless_factory", {"build_speed": .14, "energy": .08}),
        ],
        [
            ("Żebra pancerza", "armor_ribs", {"hull": .06}),
            ("Moduł ładunkowy", "cargo_module", {"capacity": .08}),
            ("Czerwony reaktor", "red_reactor", {"energy": .10}),
            ("Forteca orbitalna", "orbital_fortress", {"hull": .12, "capacity": .08}),
        ],
        [
            ("Szyna magnetyczna", "magnetic_rail", {"attack": .05}),
            ("Algorytm łowcy", "hunter_algorithm", {"swarm_damage": .08}),
            ("Synteza wysokociśnieniowa", "pressure_synthesis", {"production_fuel": .08}),
            ("Bateria anihilacji", "annihilation_battery", {"attack": .08, "swarm_damage": .08}),
        ],
    ],
    "symbionts": [
        [
            ("Pęcherz fermentacyjny", "fermentation_bladder", {"production_fuel": .08}),
            ("Szybkie pączkowanie", "rapid_budding", {"build_speed": .08}),
            ("Złota limfa", "golden_lymph", {"production_fuel": .12}),
            ("Serce odrodzenia", "rebirth_heart", {"build_speed": .12, "energy": .08}),
        ],
        [
            ("Pamięć przodków", "ancestral_memory", {"research_speed": .08}),
            ("Ogród krzemionki", "silica_garden", {"production_crystal": .06}),
            ("Czułki zbieracza", "collector_tendrils", {"swarm_loot": .10}),
            ("Świadomość kolonii", "colony_mind", {"research_speed": .12, "swarm_loot": .08}),
        ],
        [
            ("Żywa chityna", "living_chitin", {"hull": .06}),
            ("Metabolizm próżni", "vacuum_metabolism", {"fuel_efficiency": .08}),
            ("Rozciągliwa komora", "elastic_chamber", {"capacity": .10}),
            ("Skrzydła Lewiatana", "leviathan_wings", {"hull": .10, "flight_speed": .06}),
        ],
    ],
}

# Travelling to another heritage is deliberately a long, useful investment.
# Seven independent nodes join each pair of neighboring outer branch tips.
BRIDGES = [
    [
        ("Latarnia pogranicza", "border_beacon", {"flight_speed": .03}),
        ("Soczewka syntetyczna", "synthetic_lens", {"research_speed": .03}),
        ("Przekaźnik impulsowy", "pulse_relay", {"energy": .04}),
        ("Stop pamiętający", "memory_alloy", {"hull": .04}),
        ("Układ precyzyjny", "precision_circuit", {"attack": .03}),
        ("Dok transferowy", "transfer_dock", {"capacity": .04}),
        ("Węzeł współpracy", "cooperation_node", {"build_speed": .03}),
    ],
    [
        ("Ziarno ze stali", "steel_seed", {"production_metal": .04}),
        ("Tkanka przewodząca", "conductive_tissue", {"energy": .04}),
        ("Rdzeń adaptacyjny", "adaptive_core", {"hull": .04}),
        ("Łowca śladów", "trail_hunter", {"swarm_damage": .04}),
        ("Komora odzysku", "recovery_chamber", {"fuel_efficiency": .03}),
        ("Złącze symbiotyczne", "symbiotic_joint", {"build_speed": .03}),
        ("Żywy kondensator", "living_capacitor", {"production_fuel": .04}),
    ],
    [
        ("Zarodnik gwiezdny", "star_spore", {"flight_speed": .03}),
        ("Czułek grawitacyjny", "gravity_tendril", {"capacity": .04}),
        ("Błona zwierciadlana", "mirror_membrane", {"hull": .04}),
        ("Echo kryształów", "crystal_echo", {"swarm_loot": .04}),
        ("Neurony światła", "light_neurons", {"research_speed": .03}),
        ("Pąk rezonansowy", "resonant_bud", {"production_crystal": .04}),
        ("Most świadomości", "consciousness_bridge", {"energy": .04}),
    ],
]


def _description(effects):
    result = ". ".join(f"{EFFECT_LABELS[key]} +{round(value * 100)}%"
                       for key, value in effects.items()) + "."
    if "swarm_loot" in effects:
        result += " Do wysokości zapasu i ładowni; zaokrąglane w dół."
    return result


def _position(radius, angle):
    radians = math.radians(angle)
    return round(radius * math.cos(radians), 3), round(radius * math.sin(radians), 3)


def _make_graph():
    nodes, edges = [], []
    root_data = {
        "zetans": ("Przebudzenie Zety", {"first_volley": .35}),
        "automatons": ("Niezłomny rdzeń", {"damage_reduction": .12}),
        "symbionts": ("Wieczne odradzanie", {"regeneration": .35}),
    }
    for sector in SECTORS:
        race, angle = sector["race_id"], sector["angle"]
        name, effects = root_data[race]
        x, y = _position(420, angle)
        nodes.append({"id": ROOTS[race], "race_id": race, "name": name,
                      "description": _description(effects), "x": x, "y": y,
                      "size": 100, "kind": "root", "cost": 45, "effects": effects,
                      "icon": race + "_signature", "art_key": f"races/{race}/portrait"})
        for branch, offset in enumerate((-24, 0, 24)):
            previous = ROOTS[race]
            for step, (name, icon, effects) in enumerate(BRANCHES[race][branch]):
                node_id = f"{race}_{branch}_{step}"
                x, y = _position((620, 800, 980, 1160)[step], angle + offset)
                nodes.append({"id": node_id, "race_id": race, "name": name,
                              "description": _description(effects), "x": x, "y": y,
                              "size": 52 if step == 3 else 38,
                              "kind": "major" if step == 3 else "minor",
                              "cost": (6, 10, 16, 24)[step], "effects": effects,
                              "icon": icon, "art_key": f"skills/{race}/{icon}"})
                edges.append([previous, node_id])
                previous = node_id
    for pair, sector in enumerate(SECTORS):
        race = sector["race_id"]
        next_race = SECTORS[(pair + 1) % 3]["race_id"]
        start_angle = sector["angle"] + 24
        previous = f"{race}_2_3"
        for step, (name, icon, effects) in enumerate(BRIDGES[pair]):
            node_id = f"shared_{pair}_{step}"
            x, y = _position(1160, start_angle + (step + 1) * 9)
            nodes.append({"id": node_id, "race_id": "shared", "name": name,
                          "description": _description(effects), "x": x, "y": y,
                          "size": 34, "kind": "bridge", "cost": 12,
                          "effects": effects, "icon": icon,
                          "art_key": f"skills/shared/{icon}",
                          "between": [race, next_race]})
            edges.append([previous, node_id])
            previous = node_id
        edges.append([previous, f"{next_race}_0_3"])
    return {"nodes": nodes, "edges": edges, "roots": dict(ROOTS),
            "sectors": copy.deepcopy(SECTORS), "empty_radius": EMPTY_RADIUS}


_GRAPH = _make_graph()
_NODES = {node["id"]: node for node in _GRAPH["nodes"]}
_NEIGHBORS = {node_id: set() for node_id in _NODES}
for _a, _b in _GRAPH["edges"]:
    _NEIGHBORS[_a].add(_b)
    _NEIGHBORS[_b].add(_a)


def graph():
    """Return an independent, JSON-ready graph; ``size`` is a world-space radius."""
    return copy.deepcopy(_GRAPH)


def unlocked_for(race, raw_unlocks):
    """Normalize stored IDs, add the own root, discard invalid/disconnected IDs.

    The automatic root never supplies spendable currency. An unchosen race has
    neither a root nor any effective skills, even if its save contains IDs.
    """
    if not isinstance(race, str) or race not in ROOTS:
        return []
    allowed = {item for item in raw_unlocks if isinstance(item, str) and item in _NODES} \
        if isinstance(raw_unlocks, (list, tuple, set)) else set()
    root = ROOTS[race]
    allowed.add(root)
    connected, pending = {root}, [root]
    while pending:
        for neighbor in _NEIGHBORS[pending.pop()]:
            if neighbor in allowed and neighbor not in connected:
                connected.add(neighbor)
                pending.append(neighbor)
    return [node_id for node_id in _NODES if node_id in connected]


@lru_cache(maxsize=512)
def _cached_bonuses(unlocked):
    result = {key: 0.0 for key in BONUS_CAPS}
    for node_id in unlocked:
        for key, value in _NODES[node_id]["effects"].items():
            result[key] += value
    return tuple((key, round(min(BONUS_CAPS[key], value), 6)) for key, value in result.items())


def bonuses(race, raw_unlocks):
    """Aggregate each unique connected skill once, enforcing documented caps.

    Repeated production ticks reuse a bounded cache. Return a new dictionary so
    callers cannot corrupt either the model or a later player's bonuses.
    """
    return dict(_cached_bonuses(tuple(unlocked_for(race, raw_unlocks))))


def _wallet(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Nieprawidłowy stan kryształów Roju.")
    return value


def quote_unlock(race, raw_unlocks, node_id, wallet):
    """Validate one adjacent purchase; raise ``ValueError`` with a UI-safe reason."""
    if not isinstance(race, str) or race not in ROOTS:
        raise ValueError("Najpierw wybierz rasę swojego imperium.")
    if not isinstance(node_id, str) or node_id not in _NODES:
        raise ValueError("Nie ma takiej umiejętności.")
    current = unlocked_for(race, raw_unlocks)
    owned = set(current)
    if node_id in owned:
        raise ValueError("Ta umiejętność jest już odblokowana.")
    if not _NEIGHBORS[node_id].intersection(owned):
        raise ValueError("Najpierw odblokuj sąsiednią umiejętność połączoną ścieżką.")
    balance, cost = _wallet(wallet), _NODES[node_id]["cost"]
    if balance < cost:
        raise ValueError(f"Brakuje {cost - balance} kryształów Roju. Zdobądź je, atakując Rój.")
    return {"node_id": node_id, "cost": cost, "balance_after": balance - cost,
            "unlocks": unlocked_for(race, current + [node_id])}


def public_state(race, raw_unlocks, wallet):
    """Graph, balance and authoritative node eligibility for the touch client."""
    balance = _wallet(wallet)
    unlocked = unlocked_for(race, raw_unlocks)
    owned = set(unlocked)
    result = graph()
    for node in result["nodes"]:
        node["unlocked"] = node["id"] in owned
        node["available"] = not node["unlocked"] and bool(_NEIGHBORS[node["id"]].intersection(owned))
        node["affordable"] = node["available"] and balance >= node["cost"]
    result.update(balance=balance, unlocked=unlocked, bonuses=bonuses(race, unlocked))
    return result
