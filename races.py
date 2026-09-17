"""Alien Colonies playable factions: independent authoritative balance catalog.

Tuple layouts match the legacy roles. Internal role keys deliberately stay stable;
every faction supplies its own names, art, costs, construction times and ship stats.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t

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


# These are additional structures, not renamed economy roles. Ownership of an
# empire's race (never a foreign skill root) selects its local building catalog.
UNIQUE_BUILDINGS = {
    "zetans": {
        "phase_matrix": {
            "spec": ("Matryca Fazowa", "Stabilizuje pole wydobycia i zmniejsza pobór energii kopalń oraz destylatora w tej kolonii.", (420, 380, 80), 220),
            "requirements": (), "effect": "mining_energy_reduction", "per_level": .06, "cap": .30,
        },
        "echo_observatory": {
            "spec": ("Obserwatorium Echa", "Odczytuje echa układów. Zwiad wysłany z tej kolonii trwa krócej.", (720, 960, 180), 340),
            "requirements": (("lab", 2),), "effect": "scout_time_reduction", "per_level": .08, "cap": .40,
        },
        "synapse_archive": {
            "spec": ("Archiwum Synaps", "Po ukończeniu badań oddaje część kryształów", (940, 1250, 250), 420),
            "requirements": (("lab", 2),), "effect": "research_crystal_refund", "per_level": .03, "cap": .15,
        },
    },
    "automatons": {
        "serial_forge": {
            "spec": ("Kuźnia Seryjna", "Przyspiesza budowę partii statków w tej kolonii. Jeden statek powstaje w zwykłym czasie.", (560, 240, 100), 200),
            "requirements": (), "effect": "batch_time_reduction_per_extra", "per_level": .015, "cap": .075,
        },
        "magnetic_citadel": {
            "spec": ("Cytadela Magnetyczna", "Wzmacnia pierwszą salwę floty broniącej tej kolonii. Nie wspomaga wysłanych ataków.", (1250, 560, 200), 330),
            "requirements": (("shipyard", 2),), "effect": "defense_first_volley", "per_level": .12, "cap": .60,
        },
        "wreck_recycler": {
            "spec": ("Recykler Wraków", "Zwycięska flota wysłana z tej kolonii odzyskuje metal z wraków wroga. Ładownia jest ograniczona; Kryształy Roju mają pierwszeństwo.", (1050, 680, 240), 360),
            "requirements": (("shipyard", 2),), "effect": "wreck_recovery_fraction", "per_level": .05, "cap": .25,
        },
    },
    "symbionts": {
        "world_root": {
            "spec": ("Korzeń Świata", "Przyspiesza budowę wszystkich budynków tej kolonii na każdym poziomie.", (380, 230, 150), 240),
            "requirements": (), "effect": "building_time_reduction", "per_level": .08, "cap": .40,
        },
        "pioneer_nursery": {
            "spec": ("Zarodnia Pionierów", "Wyprawy z tej kolonii zakładają nowe kolonie z wyższymi poziomami czterech budynków gospodarczych.", (680, 450, 320), 370),
            "requirements": (("shipyard", 2),), "effect": "colony_start_building_bonus", "per_level": 1, "cap": 5,
        },
        "renewal_grove": {
            "spec": ("Gaj Odnowy", "Zwiększa regenerację statków broniących planety z Gajem.", (860, 650, 400), 440),
            "requirements": (("lab", 2),), "effect": "renewal_fraction", "per_level": .02, "cap": .10,
        },
    },
}


UNIQUE_RESEARCH = {
    "zetans": {
        "antigravity": {
            "spec": ("Antygrawitacja", "Cała flota lata o 20% szybciej za każdy poziom. Łączy się z napędem i umiejętnościami; przyspiesza nowe wyprawy.", (1200, 1800, 450), 600),
            "requirements": (("lab", 3), ("echo_observatory", 2)),
        },
    },
    "symbionts": {
        "multiplication": {
            "spec": ("Namnażanie", "Rozmnaża całą posiadaną flotę, także w podróży, i zwiększa liczbę hodowanych statków. Każdy poziom podnosi mnożnik o 0,2; części kolejnego statku zachowują się na później.", (1400, 1100, 900), 600),
            "requirements": (("lab", 3), ("renewal_grove", 2)),
        },
    },
    "automatons": {
        "recycling": {
            "spec": ("Recykling", "Każdy poziom zwraca 5% zapłaconych materiałów po ukończeniu budynku, ulepszenia lub partii statków. Zwrot ustala się przy zamówieniu; nie obejmuje badań.", (1800, 1300, 500), 600),
            "requirements": (("lab", 3), ("wreck_recycler", 2)),
        },
    },
}


# 0.5.0 adds midgame choices without replacing the original racial signatures.
EXPANSION_BUILDINGS = {'zetans': {'quantum_foundry': {'spec': ('Kuźnia Kwantowa',
                                         'Skraca czas budowy wszystkich statków w tej kolonii.',
                                         (1500, 1700, 350),
                                         540),
                                'requirements': (('shipyard', 2), ('lab', 2)),
                                'effect': 'ship_time_reduction',
                                'per_level': 0.05,
                                'cap': 0.25},
            'phase_vault': {'spec': ('Skarbiec Fazowy',
                                     'Chroni część każdego zwykłego surowca przed grabieżą.',
                                     (1100, 1550, 250),
                                     480),
                            'requirements': (('lab', 2),),
                            'effect': 'protected_resources',
                            'per_level': 1500,
                            'cap': 7500},
            'gravitic_logistics': {'spec': ('Węzeł Grawitacyjny',
                                            'Zmniejsza zużycie paliwa wypraw z tej kolonii.',
                                            (1800, 2250, 500),
                                            660),
                                   'requirements': (('shipyard', 3), ('lab', 3)),
                                   'effect': 'fleet_fuel_reduction',
                                   'per_level': 0.04,
                                   'cap': 0.2}},
 'symbionts': {'brood_chamber': {'spec': ('Komora Lęgowa',
                                          'Skraca czas hodowli wszystkich statków w tej kolonii.',
                                          (1400, 1100, 850),
                                          660),
                                 'requirements': (('shipyard', 2), ('lab', 2)),
                                 'effect': 'ship_time_reduction',
                                 'per_level': 0.05,
                                 'cap': 0.25},
               'living_vault': {'spec': ('Żywy Skarbiec',
                                         'Chroni część każdego zwykłego surowca przed grabieżą.',
                                         (1050, 950, 600),
                                         600),
                                'requirements': (('lab', 2),),
                                'effect': 'protected_resources',
                                'per_level': 1500,
                                'cap': 7500},
               'nutrient_reservoir': {'spec': ('Zbiornik Odżywczy',
                                               'Zwiększa produkcję metalu, kryształów i paliwa w tej kolonii.',
                                               (1900, 1450, 1000),
                                               780),
                                      'requirements': (('refinery', 3), ('lab', 3)),
                                      'effect': 'production_all',
                                      'per_level': 0.04,
                                      'cap': 0.2}},
 'automatons': {'assembly_hub': {'spec': ('Centrum Montażowe',
                                          'Skraca czas budowy wszystkich statków w tej kolonii.',
                                          (2300, 1150, 400),
                                          480),
                                 'requirements': (('shipyard', 2), ('lab', 2)),
                                 'effect': 'ship_time_reduction',
                                 'per_level': 0.05,
                                 'cap': 0.25},
                'armored_vault': {'spec': ('Skarbiec Pancerny',
                                           'Chroni część każdego zwykłego surowca przed grabieżą.',
                                           (1850, 850, 300),
                                           420),
                                  'requirements': (('lab', 2),),
                                  'effect': 'protected_resources',
                                  'per_level': 1500,
                                  'cap': 7500},
                'ore_processor': {'spec': ('Przetwórnia Rudy',
                                           'Zwiększa produkcję metalu w tej kolonii.',
                                           (2700, 1250, 450),
                                           600),
                                  'requirements': (('metal_mine', 3), ('lab', 3)),
                                  'effect': 'production_metal',
                                  'per_level': 0.06,
                                  'cap': 0.3}}}

EXPANSION_RESEARCH = {'zetans': {'phase_hulls': {'spec': ('Kadłuby Fazowe',
                                     'Zwiększa wytrzymałość wszystkich statków o 8% na poziom.',
                                     (1600, 2300, 500),
                                     780),
                            'requirements': (('lab', 3), ('quantum_foundry', 1)),
                            'effect': 'hull',
                            'per_level': 0.08,
                            'cap': 0.4},
            'coherent_plasma': {'spec': ('Plazma Koherentna',
                                         'Zwiększa atak wszystkich statków o 8% na poziom.',
                                         (2100, 2800, 700),
                                         960),
                                'requirements': (('lab', 4), ('quantum_foundry', 2), ('research', 'weapons', 2)),
                                'effect': 'attack',
                                'per_level': 0.08,
                                'cap': 0.4},
            'folding_cargo': {'spec': ('Składane Ładownie',
                                       'Zwiększa ładowność wszystkich statków o 12% na poziom.',
                                       (1400, 1900, 450),
                                       720),
                              'requirements': (('lab', 3), ('phase_vault', 1)),
                              'effect': 'capacity',
                              'per_level': 0.12,
                              'cap': 0.6}},
 'symbionts': {'chitin_layers': {'spec': ('Warstwy Chitynowe',
                                          'Zwiększa wytrzymałość wszystkich statków o 10% na poziom.',
                                          (1750, 1300, 1150),
                                          900),
                                 'requirements': (('lab', 3), ('brood_chamber', 1)),
                                 'effect': 'hull',
                                 'per_level': 0.1,
                                 'cap': 0.5},
               'corrosive_spores': {'spec': ('Żrące Zarodniki',
                                             'Zwiększa atak wszystkich statków o 8% na poziom.',
                                             (2200, 1700, 1350),
                                             1080),
                                    'requirements': (('lab', 4), ('brood_chamber', 2), ('research', 'weapons', 2)),
                                    'effect': 'attack',
                                    'per_level': 0.08,
                                    'cap': 0.4},
               'metabolic_drive': {'spec': ('Napęd Metaboliczny',
                                            'Zmniejsza zużycie paliwa całej floty o 6% na poziom.',
                                            (1600, 1150, 1050),
                                            840),
                                   'requirements': (('lab', 3), ('nutrient_reservoir', 1)),
                                   'effect': 'fuel_efficiency',
                                   'per_level': 0.06,
                                   'cap': 0.3}},
 'automatons': {'composite_armor': {'spec': ('Pancerz Kompozytowy',
                                             'Zwiększa wytrzymałość wszystkich statków o 10% na poziom.',
                                             (2850, 1400, 500),
                                             660),
                                    'requirements': (('lab', 3), ('assembly_hub', 1)),
                                    'effect': 'hull',
                                    'per_level': 0.1,
                                    'cap': 0.5},
                'siege_algorithms': {'spec': ('Algorytmy Oblężnicze',
                                              'Zwiększa atak wszystkich statków o 8% na poziom.',
                                              (3500, 1700, 650),
                                              840),
                                     'requirements': (('lab', 4), ('assembly_hub', 2), ('research', 'weapons', 2)),
                                     'effect': 'attack',
                                     'per_level': 0.08,
                                     'cap': 0.4},
                'modular_cargo': {'spec': ('Ładownie Modułowe',
                                           'Zwiększa ładowność wszystkich statków o 12% na poziom.',
                                           (2350, 1250, 400),
                                           600),
                                  'requirements': (('lab', 3), ('armored_vault', 1)),
                                  'effect': 'capacity',
                                  'per_level': 0.12,
                                  'cap': 0.6}}}

EXPANSION_SHIPS = {'zetans': {'interceptor': ('Błysk',
                            'Bardzo szybki dysk uderzeniowy do krótkich najazdów. Lekki kadłub wymaga ostrożności.',
                            (800, 1050, 220),
                            250,
                            68,
                            155,
                            90,
                            4,
                            2.65),
            'siege': ('Zaćmienie',
                      'Powolny okręt oblężniczy. Atak +50% podczas szturmu na bronioną planetę Roju.',
                      (5400, 6800, 1550),
                      1500,
                      540,
                      1200,
                      350,
                      30,
                      0.7),
            'freighter': ('Arka Horyzontu',
                          'Wielka ładownia do handlu i transportu. Potrzebuje eskorty.',
                          (2100, 2200, 500),
                          600,
                          8,
                          260,
                          7000,
                          7,
                          1.05)},
 'symbionts': {'interceptor': ('Kolec Próżni',
                               'Szybki żywy drapieżnik do krótkich najazdów. Twardszy, lecz wolniejszy od dysków '
                               'Zetan.',
                               (850, 650, 500),
                               340,
                               54,
                               240,
                               120,
                               3,
                               1.85),
               'siege': ('Pożeracz',
                         'Żywy okręt oblężniczy. Atak +50% podczas szturmu na bronioną planetę Roju.',
                         (5600, 4200, 3500),
                         1920,
                         440,
                         2050,
                         500,
                         24,
                         0.5),
               'freighter': ('Wędrowna Macierz',
                             'Żywy transportowiec o największej ładowni. Powolny i zależny od eskorty.',
                             (2000, 1350, 1150),
                             780,
                             6,
                             440,
                             9500,
                             6,
                             0.7)},
 'automatons': {'interceptor': ('Szpon',
                                'Szybka platforma przechwytująca. Mocny kadłub kosztem większego spalania.',
                                (1200, 650, 350),
                                220,
                                65,
                                285,
                                80,
                                7,
                                1.65),
                'siege': ('Młot Oblężniczy',
                          'Ciężka artyleria orbitalna. Atak +50% podczas szturmu na bronioną planetę Roju.',
                          (8400, 3850, 2100),
                          1320,
                          560,
                          2350,
                          400,
                          45,
                          0.45),
                'freighter': ('Karawana',
                              'Pancerny transportowiec dalekiego zasięgu. Duża ładownia wymaga eskorty.',
                              (3150, 1400, 800),
                              540,
                              9,
                              500,
                              8500,
                              12,
                              0.6)}}

SHIP_REQUIREMENTS = {'zetans': {'interceptor': (('shipyard', 3), ('research', 'phase_hulls', 1)),
            'siege': (('shipyard', 6), ('quantum_foundry', 3), ('research', 'coherent_plasma', 2)),
            'freighter': (('shipyard', 4), ('phase_vault', 1), ('research', 'folding_cargo', 1))},
 'symbionts': {'interceptor': (('shipyard', 3), ('research', 'chitin_layers', 1)),
               'siege': (('shipyard', 6), ('brood_chamber', 3), ('research', 'corrosive_spores', 2)),
               'freighter': (('shipyard', 4), ('living_vault', 1), ('research', 'metabolic_drive', 1))},
 'automatons': {'interceptor': (('shipyard', 3), ('research', 'composite_armor', 1)),
                'siege': (('shipyard', 6), ('assembly_hub', 3), ('research', 'siege_algorithms', 2)),
                'freighter': (('shipyard', 4), ('armored_vault', 1), ('research', 'modular_cargo', 1))}}

SHIP_TRAITS = {'siege': {'swarm_attack_multiplier': 1.5}}

for _race_id in RACES:
    UNIQUE_BUILDINGS[_race_id].update(EXPANSION_BUILDINGS[_race_id])
    UNIQUE_RESEARCH[_race_id].update(EXPANSION_RESEARCH[_race_id])
    RACES[_race_id]["ships"].update(EXPANSION_SHIPS[_race_id])


def research_effect_text(key, level):
    level = max(0, min(5, int(level)))
    return {
        "antigravity": t('Prędkość całej floty +{0}%').format(20 * level),
        "multiplication": t('Liczebność floty i hodowli ×{0:g}').format(1 + 0.2 * level),
        "recycling": t('Zwrot materiałów z budowy: {0}%').format(5 * level),
        "phase_hulls": t('Wytrzymałość floty +{0}%').format(8 * level),
        "coherent_plasma": t('Atak floty +{0}%').format(8 * level),
        "folding_cargo": t('Ładowność floty +{0}%').format(12 * level),
        "chitin_layers": t('Wytrzymałość floty +{0}%').format(10 * level),
        "corrosive_spores": t('Atak floty +{0}%').format(8 * level),
        "metabolic_drive": t('Zużycie paliwa floty −{0}%').format(6 * level),
        "composite_armor": t('Wytrzymałość floty +{0}%').format(10 * level),
        "siege_algorithms": t('Atak floty +{0}%').format(8 * level),
        "modular_cargo": t('Ładowność floty +{0}%').format(12 * level),
    }[key]


def unique_effect_text(key, level):
    """Short local effect labels shared by all clients through the catalog."""
    level = max(0, min(5, int(level)))
    templates = {
        "echo_observatory": t('Czas zwiadu −{0}%').format(8 * level),
        "phase_matrix": t('Zużycie energii wydobycia −{0}%').format(6 * level),
        "synapse_archive": t('Zwrot zwykłych kryształów z badań: {0}%').format(3 * level),
        "serial_forge": t('Partia: −{0:g}% czasu za kolejny statek, maks. −30%').format(1.5 * level),
        "magnetic_citadel": t('Pierwsza salwa obrony +{0}%').format(12 * level),
        "wreck_recycler": t('Odzysk metalu z wraków wroga: {0}%').format(5 * level),
        "world_root": t('Czas budowy wszystkich budynków: −{0}%').format(8 * level),
        "pioneer_nursery": t('Cztery budynki gospodarcze nowej kolonii: poziom {0}').format(1 + level),
        "renewal_grove": t('Regeneracja obrony planety +{0} pkt proc.').format(2 * level),
        "quantum_foundry": t('Czas budowy statków −{0}%').format(5 * level),
        "phase_vault": t('Chroni po {0} każdego surowca').format(1500 * level),
        "gravitic_logistics": t('Zużycie paliwa wypraw −{0}%').format(4 * level),
        "brood_chamber": t('Czas hodowli statków −{0}%').format(5 * level),
        "living_vault": t('Chroni po {0} każdego surowca').format(1500 * level),
        "nutrient_reservoir": t('Produkcja wszystkich surowców +{0}%').format(4 * level),
        "assembly_hub": t('Czas budowy statków −{0}%').format(5 * level),
        "armored_vault": t('Chroni po {0} każdego surowca').format(1500 * level),
        "ore_processor": t('Produkcja metalu +{0}%').format(6 * level),
    }
    return templates[key]


# Keep unfamiliar racial unit names readable during the first mission.
SHIP_ROLES = {"scout": "Zwiadowca", "cargo": "Transportowiec", "colonizer": "Kolonizator",
              "frigate": "Lekki okręt bojowy", "cruiser": "Ciężki okręt bojowy",
              "interceptor": "Przechwytujący", "siege": "Okręt oblężniczy", "freighter": "Frachtowiec"}
for _race in RACES.values():
    for _key, _spec in tuple(_race["ships"].items()):
        _race["ships"][_key] = (_spec[0], t(SHIP_ROLES[_key]) + ". " + t(_spec[1]), *_spec[2:])


def art_key(race_id, role):
    """Return a client-relative resource key, never a filesystem path."""
    return f"races/{race_id}/{role}" if race_id in RACES else ""


def public_race(race_id):
    """JSON-ready race choice data; the caller deep-copies nested balance rules."""
    import copy
    race = RACES[race_id]
    result = {key: t(race[key]) for key in ("name", "description", "trait", "tradeoff", "weapon_name")}
    result.update(id=race_id, portrait_art=art_key(race_id, "portrait"),
                  colony_art=art_key(race_id, "colony"), weapon_art=art_key(race_id, "weapon"),
                  rules=copy.deepcopy(race["rules"]))
    return result
