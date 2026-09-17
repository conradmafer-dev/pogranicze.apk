#!/usr/bin/env python3
"""Pogranicze Galaktyki: authoritative, dependency-free multiplayer test server."""
from __future__ import annotations

try:
    from .i18n import t, join_text, language_scope, store_text, render_text, public_report, format_number
except ImportError:  # Flat Railway deployment.
    from i18n import t, join_text, language_scope, store_text, render_text, public_report, format_number

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
from contextlib import contextmanager
from functools import wraps
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

try:  # Both `python -m server.main` and Railway's direct app.py import work.
    from .races import NEUTRAL_RULES, RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH, SHIP_REQUIREMENTS, SHIP_TRAITS, art_key, public_race, unique_effect_text, research_effect_text
    from . import skill_tree, swarm, onboarding
    from .accounts import AccountManagementMixin
    from .backups import SQLiteBackups
    from .swarm_ai import SwarmAIMixin
except ImportError:
    from races import NEUTRAL_RULES, RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH, SHIP_REQUIREMENTS, SHIP_TRAITS, art_key, public_race, unique_effect_text, research_effect_text
    import skill_tree, swarm, onboarding
    from accounts import AccountManagementMixin
    from backups import SQLiteBackups
    from swarm_ai import SwarmAIMixin

VERSION = "0.6.0"
UPDATE_DEFAULT_VERSION = VERSION
CLIENT_VERSION_CODE = 27
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
    "interceptor": ("Przechwytywacz", "Szybki okręt do błyskawicznych wypraw bojowych.", (700, 450, 200), 270, 58, 170, 50, 5, 2.0),
    "siege": ("Okręt oblężniczy", "Ciężki okręt; jego atak przeciw broniącemu się Rojowi jest o 50% silniejszy.", (3600, 2400, 900), 900, 210, 850, 350, 22, 0.65),
    "freighter": ("Frachtowiec", "Ogromna ładownia do transportu zapasów i łupów.", (1700, 1100, 350), 540, 8, 360, 6500, 8, 0.75),
}
SYSTEM_NAMES = ["Helios", "Vega", "Orion", "Lyra", "Nadir", "Aster", "Talos", "Iris", "Atlas", "Selene", "Draco", "Aurora", "Kronos", "Eos", "Polaris", "Mira", "Nexus", "Arden", "Ereb", "Cygnus", "Boreas", "Zefir", "Tytan", "Perseusz", "Arka", "Solara", "Kepler", "Andara", "Vesper", "Rubież"]
MAX_RESOURCE = 1_000_000_000
MAX_BODY = 16_384
MAX_COLONIES = 12
WELCOME_REPORT_TEXT = 'Rozwijaj kolonię, badania i flotę swojej rasy. Przed wyprawą po Kryształy Roju zbadaj obronę ula: to silna twierdza, która po przegranej odbudowuje obronę. Łup otrzymasz po powrocie ocalałej floty. Rój czasem napada po zwykłe surowce; ochrona nowych graczy trwa 24 godziny. Zwykłe kryształy służą gospodarce, a rzadkie Kryształy Roju — umiejętnościom w kole.'

PRIVACY_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="robots" content="index,follow">\n<title>Alien Colonies — Privacy Policy / Polityka prywatności</title>\n<style>\n:root{color-scheme:dark;background:#07110d;color:#e7f3ea;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}body{margin:0;background:#07110d}main{max-width:920px;margin:auto;padding:32px 20px 64px}.card{background:#0d2118;border:1px solid #254638;border-radius:18px;padding:24px;margin:18px 0}h1{font-size:2rem;margin:.2em 0}.muted{color:#a9bdb1}h2{color:#bce9c7;margin-top:1.4em}h3{color:#d8eadc}a{color:#8fd7a1}code{background:#08150f;padding:.15em .35em;border-radius:5px}li{margin:.45em 0;line-height:1.55}p{line-height:1.6}.pill{display:inline-block;background:#18382a;border:1px solid #2c5a43;border-radius:999px;padding:6px 10px;margin-right:7px}.lang{margin-top:12px}.warning{border-left:4px solid #d6a85f;padding-left:14px}</style>\n</head>\n<body><main>\n<div class="card">\n<h1>Alien Colonies — Privacy Policy</h1>\n<p class="muted">Effective date: 14 September 2026</p>\n<p><span class="pill">Android game</span><span class="pill">Multiplayer backend</span></p>\n<p>Operator: the developer of <strong>Alien Colonies</strong>. Privacy contact: <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n<p>This policy explains how Alien Colonies processes information when you use the Android game, its multiplayer server and the public account/privacy pages hosted with the service.</p>\n\n<h2>1. Information processed in the current account system</h2>\n<ul>\n<li><strong>Empire/account name.</strong> It is used to identify the account and can be visible to other players in the galaxy and in multiplayer reports. Do not use sensitive real-world information as your empire name.</li>\n<li><strong>Authentication data.</strong> The server stores a salted password hash, not the plain-text password. Session tokens are stored as cryptographic hashes with expiry times. If you create a recovery code, only its hash is retained after it is shown to you.</li>\n<li><strong>No email is required by the current username-and-password registration.</strong> The email address shown in this policy is the developer contact address, not a player-account field.</li>\n<li><strong>Gameplay and save data.</strong> This includes your race, planets, resources, buildings, research, ships, fleets, skill progression, protection timers, reports, actions and other information needed to maintain your multiplayer empire.</li>\n<li><strong>Technical connection data.</strong> An IP address and request metadata are necessarily processed to deliver network traffic, apply rate limits and protect the service from abuse. The game server is designed not to write passwords, bearer tokens, request bodies or full query strings to its own request logs. Hosting and network providers may process ordinary infrastructure metadata as part of operating the service.</li>\n</ul>\n\n<h2>2. Why the data is used</h2>\n<ul>\n<li>to create, authenticate and recover accounts;</li>\n<li>to keep the multiplayer galaxy and your progress synchronized;</li>\n<li>to provide game reports, combat, trading/transport and other multiplayer features;</li>\n<li>to prevent abuse, excessive requests and unauthorized account access;</li>\n<li>to maintain backups, diagnose service failures and keep the service secure;</li>\n<li>to comply with applicable legal obligations.</li>\n</ul>\n\n<h2>3. Service providers and sharing</h2>\n<p>Alien Colonies does not sell player personal data. Data may be processed by infrastructure providers needed to operate and distribute the game, including <strong>Railway</strong> for server hosting and <strong>Google Play</strong> for Android distribution. These providers may process technical information under their own terms and privacy policies.</p>\n\n<h2>4. Optional Google sign-in</h2>\n<p>If a version of Alien Colonies offers <strong>Sign in with Google</strong> and you choose to use it, the service may receive a Google account identifier and profile information that Google is permitted to provide, such as your email address and profile name. This information would be used only to sign you in, link an existing Alien Colonies account, recover access and reduce accidental duplicate accounts. Alien Colonies never receives your Google password.</p>\n\n<h2>5. Advertising</h2>\n<p>Some versions of Alien Colonies may include advertising through <strong>Google AdMob</strong>. When advertising is enabled in the installed version, Google and its advertising partners may process device identifiers, IP address, approximate location derived from IP, ad interaction data and other technical information for ad delivery, measurement, fraud prevention and, where permitted and consented to, personalization. Consent choices may be collected through Google\'s consent tools where required.</p>\n<p class="warning"><strong>If the installed version does not display ads, this advertising processing is not active in that version.</strong> The Google Play “contains ads” declaration and Data safety form should always reflect the actual released build.</p>\n\n<h2>6. Retention and account deletion</h2>\n<p>Active account and gameplay data are kept while the account exists and while needed to operate the multiplayer service. Session records expire automatically. The standard server keeps a rotating set of hourly disaster-recovery backups; deleted information may remain temporarily in those backups until they rotate out.</p>\n<p>You can permanently delete the account and empire from the in-game account settings. A web deletion option is also available at <a href="/delete-account">/delete-account</a>. Deletion removes the active account, credentials, sessions, recovery record, colonies and fleets. A public empire name may remain temporarily in historical multiplayer reports already stored for other players until those reports rotate out, and residual copies may remain in short-lived backups.</p>\n\n<h2>7. Security</h2>\n<p>Alien Colonies uses HTTPS in hosted operation, password hashing, hashed session tokens, rate limiting and restricted server logging. No internet service can guarantee absolute security, so use a unique password and keep recovery codes private.</p>\n\n<h2>8. Your choices</h2>\n<p>You may stop using the service, log out other devices, change your password, replace your recovery code, or delete the account. Questions about privacy or deletion can be sent to <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n\n<h2>9. Changes to this policy</h2>\n<p>This policy may be updated when Alien Colonies adds or removes features, providers, sign-in methods or advertising. The effective date at the top of this page will be updated when material changes are made.</p>\n</div>\n\n<div class="card" lang="pl">\n<h1>Alien Colonies — Polityka prywatności</h1>\n<p class="muted">Data obowiązywania: 14 września 2026 r.</p>\n<p>Operator: twórca gry <strong>Alien Colonies</strong>. Kontakt w sprawach prywatności: <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n<p>Niniejsza polityka opisuje przetwarzanie informacji podczas korzystania z gry Alien Colonies na Androidzie, serwera multiplayer oraz publicznych stron dotyczących prywatności i usuwania konta.</p>\n\n<h2>1. Dane przetwarzane w obecnym systemie kont</h2>\n<ul>\n<li><strong>Nazwa imperium/konta.</strong> Służy do identyfikacji konta i może być widoczna dla innych graczy w galaktyce oraz raportach multiplayer. Nie wpisuj w nazwie imperium wrażliwych danych z życia prywatnego.</li>\n<li><strong>Dane uwierzytelniające.</strong> Serwer przechowuje solony skrót hasła, a nie hasło w postaci jawnej. Tokeny sesji są przechowywane jako skróty kryptograficzne z terminem ważności. Po utworzeniu kodu odzyskiwania serwer zachowuje wyłącznie jego skrót.</li>\n<li><strong>Obecna rejestracja nazwą i hasłem nie wymaga adresu e-mail.</strong> Adres e-mail na tej stronie jest adresem kontaktowym twórcy, a nie polem konta gracza.</li>\n<li><strong>Dane rozgrywki i zapisu.</strong> Obejmują m.in. rasę, planety, zasoby, budynki, badania, statki, floty, rozwój umiejętności, ochronę nowego gracza, raporty, wykonane akcje oraz inne informacje potrzebne do utrzymania imperium multiplayer.</li>\n<li><strong>Techniczne dane połączenia.</strong> Adres IP i metadane żądania są przetwarzane w zakresie niezbędnym do transmisji sieciowej, ograniczania liczby żądań i ochrony przed nadużyciami. Serwer gry jest zaprojektowany tak, aby we własnych logach żądań nie zapisywać haseł, tokenów Bearer, treści żądań ani pełnych parametrów zapytań. Dostawcy hostingu i sieci mogą przetwarzać zwykłe metadane infrastruktury podczas świadczenia usługi.</li>\n</ul>\n\n<h2>2. Cele przetwarzania</h2>\n<ul>\n<li>tworzenie, uwierzytelnianie i odzyskiwanie kont;</li>\n<li>utrzymywanie galaktyki multiplayer i synchronizacja postępów;</li>\n<li>realizacja raportów, walk, transportu i pozostałych funkcji multiplayer;</li>\n<li>ochrona przed nadużyciami, nadmierną liczbą żądań i nieautoryzowanym dostępem;</li>\n<li>wykonywanie kopii bezpieczeństwa, diagnozowanie awarii i zabezpieczenie usługi;</li>\n<li>realizacja obowiązków prawnych, jeśli mają zastosowanie.</li>\n</ul>\n\n<h2>3. Dostawcy usług i udostępnianie</h2>\n<p>Alien Colonies nie sprzedaje danych osobowych graczy. Dane mogą być przetwarzane przez dostawców infrastruktury niezbędnych do działania i dystrybucji gry, w szczególności <strong>Railway</strong> jako hosting serwera oraz <strong>Google Play</strong> jako platformę dystrybucji Android. Dostawcy ci mogą przetwarzać dane techniczne zgodnie z własnymi warunkami i politykami prywatności.</p>\n\n<h2>4. Opcjonalne logowanie przez Google</h2>\n<p>Jeśli dana wersja Alien Colonies udostępnia funkcję <strong>Zaloguj przez Google</strong> i zdecydujesz się jej użyć, usługa może otrzymać identyfikator konta Google oraz informacje profilowe, które Google może udostępnić, np. adres e-mail i nazwę profilu. Dane te będą wykorzystywane do logowania, połączenia z istniejącym kontem Alien Colonies, odzyskiwania dostępu i ograniczenia przypadkowego tworzenia duplikatów kont. Alien Colonies nie otrzymuje hasła do konta Google.</p>\n\n<h2>5. Reklamy</h2>\n<p>Niektóre wersje Alien Colonies mogą zawierać reklamy obsługiwane przez <strong>Google AdMob</strong>. Gdy reklamy są włączone w zainstalowanej wersji, Google i jego partnerzy reklamowi mogą przetwarzać identyfikatory urządzenia, adres IP, przybliżoną lokalizację ustalaną na podstawie IP, dane o interakcjach z reklamami i inne dane techniczne w celu wyświetlania reklam, pomiaru skuteczności, zapobiegania nadużyciom oraz — tam, gdzie jest to dozwolone i użytkownik wyrazi zgodę — personalizacji. W wymaganych regionach zgody mogą być obsługiwane przez narzędzia zgód Google.</p>\n<p class="warning"><strong>Jeżeli dana wersja gry nie wyświetla reklam, opisane przetwarzanie reklamowe nie jest w niej aktywne.</strong> Deklaracja „zawiera reklamy” i formularz Bezpieczeństwo danych w Google Play powinny zawsze odpowiadać faktycznie publikowanej wersji.</p>\n\n<h2>6. Okres przechowywania i usuwanie konta</h2>\n<p>Aktywne dane konta i rozgrywki są przechowywane tak długo, jak istnieje konto i jak długo są potrzebne do działania usługi multiplayer. Sesje wygasają automatycznie. Standardowy serwer utrzymuje rotacyjny zestaw godzinowych kopii awaryjnych; po usunięciu konta dane mogą pozostać w nich tymczasowo do czasu rotacji.</p>\n<p>Konto i całe imperium można trwale usunąć w ustawieniach konta w grze. Dostępna jest również strona internetowa <a href="/delete-account">/delete-account</a>. Usunięcie kasuje aktywne konto, dane uwierzytelniające, sesje, zapis kodu odzyskiwania, kolonie i floty. Publiczna nazwa imperium może przez pewien czas pozostawać w historycznych raportach multiplayer zapisanych u innych graczy, dopóki raporty nie zostaną usunięte przez rotację, a szczątkowe kopie mogą przez krótki czas znajdować się w kopiach bezpieczeństwa.</p>\n\n<h2>7. Bezpieczeństwo</h2>\n<p>W środowisku hostingowym Alien Colonies korzysta z HTTPS, hashowania haseł, hashowanych tokenów sesji, limitowania żądań i ograniczonego logowania serwera. Żadna usługa internetowa nie zapewnia całkowitego bezpieczeństwa, dlatego używaj unikalnego hasła i chroń kod odzyskiwania.</p>\n\n<h2>8. Twoje możliwości</h2>\n<p>Możesz przestać korzystać z usługi, wylogować inne urządzenia, zmienić hasło, zastąpić kod odzyskiwania lub usunąć konto. Pytania dotyczące prywatności lub usunięcia danych można wysłać na <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p>\n\n<h2>9. Zmiany polityki</h2>\n<p>Polityka może zostać zaktualizowana po dodaniu lub usunięciu funkcji, dostawców, metod logowania lub reklam. Przy istotnej zmianie zostanie zaktualizowana data obowiązywania podana na początku strony.</p>\n</div>\n</main></body></html>'

ACCOUNT_DELETION_HTML = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="robots" content="index,follow"><title>Alien Colonies — Delete account / Usuń konto</title>\n<style>:root{color-scheme:dark;background:#07110d;color:#e7f3ea;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}body{margin:0}main{max-width:760px;margin:auto;padding:32px 20px 64px}.card{background:#0d2118;border:1px solid #254638;border-radius:18px;padding:24px}h1{margin-top:0}label{display:block;margin:16px 0 7px;color:#bce9c7}input{box-sizing:border-box;width:100%;font:inherit;padding:13px;border-radius:10px;border:1px solid #3e6552;background:#07140e;color:#fff}button{margin-top:20px;width:100%;padding:14px;font:inherit;font-weight:700;border:0;border-radius:10px;background:#9e3f3f;color:#fff;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.muted{color:#a9bdb1;line-height:1.55}.danger{color:#ffb2a8}a{color:#8fd7a1}#status{margin-top:16px;min-height:1.5em;white-space:pre-wrap}.split{border-top:1px solid #2c4d3d;margin-top:26px;padding-top:22px}</style></head>\n<body><main><div class="card">\n<h1>Delete Alien Colonies account</h1>\n<p class="danger"><strong>This permanently deletes your active account and empire. This cannot be undone.</strong></p>\n<p class="muted">Use the same empire name and password that you use in the game. Credentials are sent directly to the Alien Colonies server over HTTPS and are not stored by this web page. You can also delete the account from the in-game Account settings.</p>\n<label for="name">Empire name / Nazwa imperium</label><input id="name" maxlength="20" autocomplete="username">\n<label for="password">Password / Hasło</label><input id="password" type="password" maxlength="128" autocomplete="current-password">\n<label for="confirm">Type exactly / Wpisz dokładnie: DELETE ACCOUNT</label><input id="confirm" maxlength="32" autocomplete="off">\n<button id="delete">Permanently delete account / Trwale usuń konto</button><div id="status" role="status" aria-live="polite"></div>\n<div class="split" lang="pl"><h2>Usuwanie konta</h2><p class="muted">Po poprawnym potwierdzeniu serwer usuwa aktywne konto, sesje, kod odzyskiwania, kolonie, floty oraz pozostałe dane imperium. Krótkotrwałe kopie awaryjne mogą wygasnąć dopiero wraz z rotacją. W razie problemu napisz na <a href="mailto:conradmafer@gmail.com">conradmafer@gmail.com</a>.</p></div>\n<p><a href="/privacy">Privacy Policy / Polityka prywatności</a></p>\n</div></main>\n<script>\n(()=>{const q=id=>document.getElementById(id),btn=q(\'delete\'),status=q(\'status\');\nconst headers=()=>({\'Content-Type\':\'application/json\',\'Accept-Language\':navigator.language||\'en\',\'X-PGR-Client-Version\':\'2100000000\'});\nbtn.addEventListener(\'click\',async()=>{const name=q(\'name\').value.trim(),password=q(\'password\').value,confirmation=q(\'confirm\').value;\nif(name.length<3||password.length<8){status.textContent=\'Enter the account name and password. / Wpisz nazwę konta i hasło.\';return}\nif(confirmation!==\'DELETE ACCOUNT\'){status.textContent=\'Type exactly: DELETE ACCOUNT\';return}\nif(!confirm(\'Permanently delete this Alien Colonies account and empire? / Trwale usunąć konto i imperium?\'))return;\nbtn.disabled=true;status.textContent=\'Deleting… / Usuwanie…\';\ntry{let r=await fetch(\'/api/login\',{method:\'POST\',headers:headers(),body:JSON.stringify({name,password})});let j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||\'Login failed\');\nlet h=headers();h.Authorization=\'Bearer \'+j.token;r=await fetch(\'/api/account/delete\',{method:\'POST\',headers:h,body:JSON.stringify({password,confirmation:\'DELETE ACCOUNT\'})});j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||\'Deletion failed\');\nq(\'password\').value=\'\';q(\'confirm\').value=\'\';status.textContent=\'Account deleted. / Konto zostało usunięte.\';btn.remove();\n}catch(e){status.textContent=\'Could not delete the account: \'+e.message+\' / Nie udało się usunąć konta.\';btn.disabled=false;}\n});})();\n</script></body></html>'


class GameError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def validate_download_url(value):
    """Check an ASCII HTTPS DNS download link; same subset as the Android client."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError(t('PGR_DOWNLOAD_URL: podaj adres HTTPS do 2048 znaków.'))
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
        raise ValueError(t('PGR_DOWNLOAD_URL: wymagany publiczny adres HTTPS bez hasła ani fragmentu #.')) from None
    return value


class UpdatePolicy:
    """Startup configuration; it neither changes nor migrates any game save."""

    def __init__(self, latest_version_code=CLIENT_VERSION_CODE, latest_version=UPDATE_DEFAULT_VERSION,
                 min_version_code=0, download_url="", message="",
                 apk_sha256="", apk_size_bytes=0):
        for name, value in (("PGR_LATEST_VERSION_CODE", latest_version_code),
                            ("PGR_MIN_VERSION_CODE", min_version_code)):
            if type(value) is not int or not 0 <= value <= MAX_VERSION_CODE:
                raise ValueError(t('{0}: podaj liczbę całkowitą od 0 do {1}.').format(name, MAX_VERSION_CODE))
        if latest_version_code < min_version_code:
            raise ValueError(t('PGR_LATEST_VERSION_CODE nie może być mniejsze od PGR_MIN_VERSION_CODE.'))
        for name, value, limit in (("PGR_LATEST_VERSION", latest_version, 40),
                                   ("PGR_UPDATE_MESSAGE", message, 300)):
            if (not isinstance(value, str) or len(value) > limit
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError(t('{0}: maksymalnie {1} znaków, bez znaków sterujących.').format(name, limit))
        if not latest_version.strip():
            raise ValueError(t('PGR_LATEST_VERSION nie może być puste.'))
        download_url = validate_download_url(download_url)
        if (not isinstance(apk_sha256, str)
                or (apk_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", apk_sha256))):
            raise ValueError("PGR_APK_SHA256: podaj 64 znaki szesnastkowe SHA-256 albo pozostaw puste.")
        if type(apk_size_bytes) is not int or not 0 <= apk_size_bytes <= MAX_APK_SIZE_BYTES:
            raise ValueError(t('PGR_APK_SIZE_BYTES: podaj liczbę całkowitą od 0 do {0}.').format(MAX_APK_SIZE_BYTES))
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
            raise ValueError(t('{0}: podaj nieujemną liczbę całkowitą.').format(name))
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
        super().__init__(t('Zaktualizuj grę, aby kontynuować.'), 426)
        self.update = policy.manifest()


def ident(prefix):
    return prefix + secrets.token_hex(8)


def integer(value, label, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise GameError(t('{0}: podaj liczbę całkowitą od {1} do {2}.').format(label, low, high))
    return value


def counts(value, valid_keys, label, maximum=1_000_000):
    if not isinstance(value, dict) or any(k not in valid_keys for k in value):
        raise GameError(t('Nieprawidłowe dane: {0}.').format(label))
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
    return math.floor(round(math.fsum(specs[key][6] * n for key, n in ships.items() if n), 6))


def atomic_mutation(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._atomic():
            return method(self, *args, **kwargs)
    return wrapped


def restore_snapshot(target, saved):
    """Restore existing containers in place so held planet/player references agree."""
    if isinstance(target, dict) and isinstance(saved, dict):
        for key in list(target):
            if key not in saved:
                del target[key]
        for key, value in saved.items():
            if key in target and isinstance(value, (dict, list)) and type(target[key]) is type(value):
                restore_snapshot(target[key], value)
            else:
                target[key] = copy.deepcopy(value)
    elif isinstance(target, list) and isinstance(saved, list):
        target[:] = copy.deepcopy(saved)


try:
    from .galaxies import UniverseMixin, BY_ID as GALAXIES_BY_ID, separation, inferred_id, JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS, JUMP_SECONDS_PER_MLY
except ImportError:
    from galaxies import UniverseMixin, BY_ID as GALAXIES_BY_ID, separation, inferred_id, JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS, JUMP_SECONDS_PER_MLY


class World(UniverseMixin, SwarmAIMixin, AccountManagementMixin):
    """All public operations are locked. advance(now) makes time injectable in tests."""

    account_error_class = GameError

    def __init__(self, db_path="galaxy.sqlite3", speed=1.0, now=None,
                 max_players=0):
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0.1 <= speed <= 1000:
            raise ValueError("speed must be finite and between 0.1 and 1000")
        if type(max_players) is not int or max_players < 0:
            raise ValueError("max_players must be a nonnegative integer (0 disables the account cap)")
        self.max_players = max_players
        self.speed = float(speed)
        self.lock = threading.RLock()
        self._atomic_depth = 0
        self.write_healthy = True
        self.backups = SQLiteBackups(db_path)
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
        self._init_account_management()
        self.db.commit()
        row = self.db.execute("SELECT body FROM snapshot WHERE id=1").fetchone()
        if row:
            self.data = json.loads(row[0])
            # Back up the committed pre-migration database before adding galaxies.
            # Refuse a disk-backed migration when its backup cannot be written.
            if self.data.get("galaxy_schema_version", 0) < 1 and self.backups.directory is not None:
                if self.backups.maybe_create(self.db, force=True) is None:
                    self.db.close()
                    raise OSError("Nie zapisano kopii przed aktualizacja galaktyk. Sprawdz wolne miejsce na Volume.")
            self.now = max(self.now, self.data["last_update"])
            self._ensure_progression()
            self._ensure_universe()
            # Existing absolute event deadlines remain valid if speed is changed.
            self.advance(self.now)
        else:
            self.data = self._new_world()
            self._save()
            self.backups.maybe_create(self.db)

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
        data = {"progression_version": 2, "last_update": self.now, "systems": systems, "planets": planets, "players": {}, "fleets": {}, "alien": {"name": t('Rój Khar'), "next_expansion_at": self.now + 120, "swarm_next_colonization_at": self.now + 7 * 86400, "swarm_next_raid_at": self.now + swarm.RAID_INTERVAL_SECONDS}}
        self._ensure_universe(data)
        return data

    def _ensure_progression(self):
        """Additive migration: no wallet grant, and existing race signatures stay active."""
        # Existing 0.4.0 worlds gain a grace period once, without reseeding NPCs.
        self.data["alien"].setdefault("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
        for player in self.data["players"].values():
            player.setdefault("swarm_crystals", 0)
            player["skill_nodes"] = skill_tree.unlocked_for(player.get("race_id", ""), player.get("skill_nodes", []))
            self._ensure_racial_research(player)
            self._ensure_legacy_report_i18n(player)
            onboarding.ensure(self.data, player)
        for planet in self.data["planets"].values():
            self._ensure_race_buildings(planet)
            for key in self._specs(planet["owner_id"], "ships"):
                planet["ships"].setdefault(key, 0)
        for fleet in self.data["fleets"].values():
            for key in self._specs(fleet["owner_id"], "ships"):
                fleet["ships"].setdefault(key, 0)
        if self.data.get("progression_version", 0) < 2:
            previous_swarm_ids = {p["id"] for p in self.data["planets"].values() if p["owner_id"] == "khar"}
            # One-time NPC frontier rebuild also gives upgraded servers real hives.
            # Player accounts/worlds remain intact; old NPC ships/queues are retired.
            for fid, fleet in list(self.data["fleets"].items()):
                if fleet["owner_id"] == "khar":
                    del self.data["fleets"][fid]
            for pid, planet in list(self.data["planets"].items()):
                if planet["owner_id"] == "khar":
                    self.data["planets"][pid] = self._planet(pid, planet["name"], planet["system_id"], planet["slot"])
            for preferred, hive in (("s14p2", True), ("s15p2", True), ("s20p2", True)):
                reference = self.data["planets"][preferred]
                empty = [p for p in self.data["planets"].values() if p["owner_type"] == "empty"]
                if not empty:
                    break
                planet = reference if reference["owner_type"] == "empty" else min(empty, key=lambda p: self._distance(reference, p))
                swarm.seed(planet, self.now, hive=hive)
            self.data["alien"]["next_expansion_at"] = self.now + 120
            self.data["alien"]["swarm_next_colonization_at"] = self.now + 7 * 86400
            self.data["progression_version"] = 2
            # Do not settle the old offline interval against newly seeded stock
            # or expose pre-upgrade player attacks to a suddenly stronger target.
            for fleet in list(self.data["fleets"].values()):
                if fleet["mission"] == "attack" and fleet["status"] == "outbound" and fleet["owner_id"] != "khar":
                    target = self.data["planets"][fleet["target_id"]]
                    if target["id"] in previous_swarm_ids or target["owner_id"] == "khar":
                        self._return(fleet)
                        self._report(fleet["owner_id"], t('Zmiana granic Roju'), t('Rój przebudował swoje gniazda. Twoja wcześniejsza wyprawa zawraca bez walki. Sprawdź nowy raport zwiadu.'))
            for player_id in self.data["players"]:
                self._report(player_id, t('Twierdze Roju'), t('Rój wycofał przyczółki i umocnił trzy ule. Kryształy odnawiają się po jednej sztuce na 18 godzin, po odbudowie obrony. Koszty koła rosną z każdym zakupem.'), "swarm/colony")

    def _ensure_legacy_report_i18n(self, player):
        """Attach safe templates to known pre-localization reports without touching names."""
        race_id = player.get("race_id", "")
        for report in player.get("reports", []):
            if isinstance(report.get("i18n"), dict):
                continue
            title = report.get("title", "")
            text = report.get("text", "")
            if title == 'Witaj w Alien Colonies' and text == WELCOME_REPORT_TEXT:
                report["i18n"] = {"title": store_text(t('Witaj w Alien Colonies')),
                                  "text": store_text(t(WELCOME_REPORT_TEXT))}
                continue
            if title != 'Narodziny cywilizacji' or race_id not in RACES:
                continue
            race = RACES[race_id]
            intro = t('Wybrano rasę: {0}. To stały wybór tego imperium.').format(t(race['name']))
            composed = intro + " " + t(race["trait"]) + " " + t(race["tradeoff"])
            if text == render_text(store_text(composed), "pl"):
                report["i18n"] = {"title": store_text(t('Narodziny cywilizacji')),
                                  "text": store_text(composed)}


    @staticmethod
    def _planet(pid, name, sid, slot):
        return {"id": pid, "name": name, "system_id": sid, "galaxy_id": inferred_id(sid), "slot": slot, "owner_type": "empty", "owner_id": "", "resources": dict.fromkeys(RESOURCES, 0.0), "buildings": dict.fromkeys(BUILDINGS, 0), "ships": blank_ships(), "queue": []}

    @contextmanager
    def _atomic(self):
        """A public mutation succeeds only when both SQL and its RAM snapshot commit.

        A failed advance restores last_update and now, so its elapsed time and
        completed events can be retried. Failed actions restore replay ids too.
        """
        with self.lock:
            if self._atomic_depth:
                self._atomic_depth += 1
                try:
                    yield
                finally:
                    self._atomic_depth -= 1
                return
            before, before_now = copy.deepcopy(self.data), self.now
            self._atomic_depth = 1
            saving = False
            try:
                self.db.execute("SAVEPOINT world_mutation")
                yield
                saving = True
                self._save(commit=False)
                self.db.execute("RELEASE SAVEPOINT world_mutation")
                self.db.commit()
            except BaseException as exc:
                rollback_failed = False
                try:
                    self.db.rollback()
                except sqlite3.Error:
                    rollback_failed = True
                finally:
                    restore_snapshot(self.data, before)
                    self.now = before_now
                if rollback_failed or saving or isinstance(exc, (sqlite3.Error, OSError)):
                    self.write_healthy = False
                    raise GameError(t('Zapis gry jest chwilowo niedostępny. Spróbuj ponownie za chwilę.'), 503) from None
                raise
            else:
                self.write_healthy = True
            finally:
                self._atomic_depth = 0
            self.backups.maybe_create(self.db)

    def _save(self, commit=True):
        try:
            body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            self.db.execute("INSERT INTO snapshot(id,body) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (body,))
            if commit and not self._atomic_depth:
                self.db.commit()
                self.write_healthy = True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            self.write_healthy = False
            raise

    def close(self):
        with self.lock:
            try:
                self._save()
            finally:
                self.db.close()

    def _race_id(self, owner_id):
        # Khar is an NPC without a skill root; its own catalog is handled in _specs.
        race_id = self.data["players"].get(owner_id, {}).get("race_id", "")
        return race_id if isinstance(race_id, str) and race_id in RACES else ""

    def _bonuses(self, owner_id):
        player = self.data["players"].get(owner_id, {})
        return skill_tree.bonuses(self._race_id(owner_id), player.get("skill_nodes", []))

    def _ensure_race_buildings(self, p):
        for key in UNIQUE_BUILDINGS.get(self._race_id(p["owner_id"]), {}):
            p["buildings"].setdefault(key, 0)

    def _ensure_racial_research(self, player):
        # New effects start at zero. Loading an old save never grows existing ships.
        for key in UNIQUE_RESEARCH.get(player.get("race_id", ""), {}):
            player["research"].setdefault(key, 0)
        player.setdefault("fleet_growth_credits", {})

    def _racial_research_level(self, owner_id, key):
        if key not in UNIQUE_RESEARCH.get(self._race_id(owner_id), {}):
            return 0
        level = self.data["players"][owner_id]["research"].get(key, 0)
        return max(0, min(5, level)) if type(level) is int else 0

    def _fleet_multiplier(self, owner_id):
        return Fraction(5 + self._racial_research_level(owner_id, "multiplication"), 5)

    @staticmethod
    def _growth_credit(player, key):
        value = player.get("fleet_growth_credits", {}).get(key, [0, 1])
        return Fraction(value[0], value[1])

    @staticmethod
    def _store_growth_credit(player, key, value):
        player.setdefault("fleet_growth_credits", {})[key] = [value.numerator, value.denominator]

    def _produced_ships(self, owner_id, key, amount):
        multiplier = self._fleet_multiplier(owner_id)
        if multiplier == 1:
            return amount
        player = self.data["players"][owner_id]
        exact = amount * multiplier + self._growth_credit(player, key)
        count = math.floor(exact)
        self._store_growth_credit(player, key, exact - count)
        return count

    def _multiply_existing_fleet(self, owner_id, old_level, new_level):
        """Grow surviving ships once; exact credits make batch size immaterial.

        Credits belong to a ship type across the empire. Whole new ships are split
        proportionally over occupied locations, with stable largest-remainder ties.
        Neither cargo nor mission identity/deadlines are copied or recalculated.
        """
        if self._race_id(owner_id) != "symbionts" or new_level <= old_level:
            return 0
        ratio = Fraction(5 + new_level, 5 + old_level)
        player = self.data["players"][owner_id]
        locations = sorted(
            [("planet:" + p["id"], p["ships"]) for p in self.data["planets"].values() if p["owner_id"] == owner_id]
            + [("fleet:" + f["id"], f["ships"]) for f in self.data["fleets"].values() if f["owner_id"] == owner_id],
            key=lambda row: row[0])
        grown = 0
        for key in self._specs(owner_id, "ships"):
            occupied = [(name, ships, ships.get(key, 0)) for name, ships in locations if ships.get(key, 0) > 0]
            total = sum(count for _, _, count in occupied)
            if not total:
                # A remembered fraction cannot resurrect a completely lost type.
                continue
            exact = (total + self._growth_credit(player, key)) * ratio
            extra = math.floor(exact) - total
            self._store_growth_credit(player, key, exact - math.floor(exact))
            shares = [extra * count // total for _, _, count in occupied]
            remaining = extra - sum(shares)
            order = sorted(range(len(occupied)), key=lambda i: (-(extra * occupied[i][2] % total), occupied[i][0]))
            for i in order[:remaining]:
                shares[i] += 1
            for (_, ships, _), share in zip(occupied, shares):
                ships[key] += share
            grown += extra
        return grown

    def _building_effects(self, p):
        """Only the owner's local structures apply; foreign skill roots do not."""
        return {meta["effect"]: round(min(meta["cap"], meta["per_level"] * max(0, min(5, p["buildings"].get(key, 0)))), 6)
                for key, meta in UNIQUE_BUILDINGS.get(self._race_id(p["owner_id"]), {}).items()}

    def _racial_research_effects(self, owner_id):
        """Empire-wide bonuses from completed research; signatures remain separate."""
        effects = {}
        for key, meta in UNIQUE_RESEARCH.get(self._race_id(owner_id), {}).items():
            if "effect" not in meta:
                continue
            value = min(meta["cap"], meta["per_level"] * self._racial_research_level(owner_id, key))
            effects[meta["effect"]] = round(effects.get(meta["effect"], 0) + value, 6)
        return effects

    def _entry_requirements(self, owner_id, planet, group, key):
        """Resolve old local-building requirements and new mixed prerequisites."""
        race_id = self._race_id(owner_id)
        if group == "ships":
            default = (("shipyard", 2 if key == "cruiser" else
                        6 if key == "siege" else 4 if key == "freighter" else
                        3 if key == "interceptor" else 1),)
            required = SHIP_REQUIREMENTS.get(race_id, {}).get(key, default)
        else:
            catalog = UNIQUE_BUILDINGS if group == "buildings" else UNIQUE_RESEARCH
            required = catalog.get(race_id, {}).get(key, {}).get("requirements", ())
            if group == "research":
                required = (*required, ("lab", 1))
        player = self.data["players"].get(owner_id, {})
        normalized = {}
        for entry in required:
            prerequisite_group, prerequisite_key, minimum = ("buildings", *entry) if len(entry) == 2 else entry
            if prerequisite_group not in ("buildings", "research"):
                raise ValueError("Unsupported prerequisite group: " + prerequisite_group)
            identity = (prerequisite_group, prerequisite_key)
            normalized[identity] = max(minimum, normalized.get(identity, 0))
        result = []
        for (prerequisite_group, prerequisite_key), minimum in normalized.items():
            specs = self._specs(owner_id, prerequisite_group)
            if prerequisite_key not in specs:
                raise ValueError("Unknown prerequisite: " + prerequisite_key)
            levels = planet["buildings"] if prerequisite_group == "buildings" else player.get("research", {})
            result.append({"group": prerequisite_group, "key": prerequisite_key,
                           "name": specs[prerequisite_key][0], "level": minimum,
                           "met": levels.get(prerequisite_key, 0) >= minimum})
        return result

    def _lootable_resources(self, planet):
        """A local vault shields each ordinary stock before the 35% loot fraction."""
        protected = self._building_effects(planet).get("protected_resources", 0)
        return {key: math.floor(max(0, planet["resources"][key] - protected) * .35)
                for key in RESOURCES}

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
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {"buildings": swarm.BUILDINGS, "ships": swarm.SHIPS, "research": swarm.RESEARCH}[group].items()}
        race_id = self._race_id(owner_id)
        specs = RACES[race_id][group] if race_id else {"buildings": BUILDINGS, "ships": SHIPS, "research": RESEARCH}[group]
        if group == "buildings" and race_id:
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {**specs, **{key: meta["spec"] for key, meta in UNIQUE_BUILDINGS[race_id].items()}}.items()}
        if group == "research" and race_id:
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in {**{key: meta["spec"] for key, meta in UNIQUE_RESEARCH[race_id].items()}, **specs}.items()}
        if group != "ships":
            return {key: (t(spec[0]), t(spec[1]), *spec[2:]) for key, spec in specs.items()}
        bonuses = self._bonuses(owner_id)
        result = {}
        research = self._racial_research_effects(owner_id)
        for key, spec in specs.items():
            values = [t(spec[0]), t(spec[1]), *spec[2:]]
            for index, effect in ((4, "attack"), (5, "hull"), (6, "capacity"), (8, "flight_speed")):
                values[index] = round(values[index] * (1.0 + bonuses.get(effect, 0)) * (1.0 + research.get(effect, 0)), 6)
            values[7] = round(values[7] * (1.0 - bonuses.get("fuel_efficiency", 0)) * (1.0 - research.get("fuel_efficiency", 0)), 6)
            result[key] = tuple(values)
        return result

    def _race_choice_reason(self, player_id):
        if self._race_id(player_id):
            return t('Rasa tego imperium została już wybrana.')
        owned_ids = {p["id"] for p in self.data["planets"].values() if p["owner_id"] == player_id}
        if any(p["queue"] for p in self.data["planets"].values() if p["id"] in owned_ids):
            return t('Poczekaj na zakończenie wszystkich projektów przed wyborem rasy.')
        if any(f["owner_id"] == player_id or f["target_id"] in owned_ids for f in self.data["fleets"].values()):
            return t('Poczekaj na zakończenie własnych lotów i misji do twoich planet przed wyborem rasy.')
        return ""

    def energy(self, p):
        b = p["buildings"]
        rules = self._rules(p["owner_id"])
        supply = b["power_plant"] * rules["energy_supply_per_level"]
        used = sum(b[key] * amount for key, amount in rules["energy_use_per_level"].items())
        used = round(used * (1 - self._building_effects(p).get("mining_energy_reduction", 0)), 6)
        return {"supply": supply, "used": used, "factor": min(1.0, supply / used) if used else 1.0}

    def production(self, p):
        factor = self.energy(p)["factor"] * self.speed
        multipliers = self._rules(p["owner_id"])["production_multipliers"]
        effects = self._building_effects(p)
        return {resource: (base + p["buildings"][key] * per_level) * factor * multipliers[resource]
                * (1 + effects.get("production_all", 0)) * (1 + effects.get("production_" + resource, 0))
                for resource, key, base, per_level in (("metal", "metal_mine", 90, 450),
                                                      ("crystal", "crystal_mine", 60, 330),
                                                      ("fuel", "refinery", 30, 180))}

    def _produce(self, dt, start_at=None):
        if dt <= 0:
            return
        start = self.now if start_at is None else start_at
        for p in self.data["planets"].values():
            if p["owner_type"] == "empty":
                continue
            elapsed = dt
            if p["owner_id"] == "khar":
                # A freshly migrated fortress cannot earn the old offline
                # interval. Player production and existing deadlines are intact.
                elapsed = max(0.0, start + dt - max(start, p.get("swarm_established_at", start)))
            for k, rate in self.production(p).items():
                p["resources"][k] = min(MAX_RESOURCE, p["resources"][k] + rate * elapsed / 3600)
            if p["owner_id"] == "khar" and self._swarm_ready(p):
                p["swarm_loot_sealed"] = False
                stage = swarm.kind(p)
                # Rare production follows real time, never the testing speed.
                stock = p.get("swarm_crystals", 0) + elapsed / swarm.CRYSTAL_REGEN_SECONDS
                if abs(stock - round(stock)) < 1e-9:
                    stock = float(round(stock))
                p["swarm_crystals"] = min(swarm.CRYSTAL_CAPS[stage], stock)

    @atomic_mutation
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
                self._produce(event_time - cursor, start_at=cursor)
                cursor = event_time
                self.now = event_time
                for p in self.data["planets"].values():
                    if p["queue"] and p["queue"][0]["ends_at"] <= event_time:
                        self._complete_queue(p)
                for fid in list(self.data["fleets"]):
                    fleet = self.data["fleets"].get(fid)
                    if fleet and fleet["arrives_at"] <= event_time:
                        self._complete_fleet(fleet)
            self._produce(now - cursor, start_at=cursor)
            self.now = now
            self.data["last_update"] = now
            if now >= self.data["alien"]["next_expansion_at"]:
                self._alien_turn()
                self.data["alien"]["next_expansion_at"] = now + max(8, 120 / self.speed)
            self.db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            self._save()

    def _complete_queue(self, p):
        if not p["queue"]:
            return
        task = p["queue"].pop(0)
        grown = 0
        if task["kind"] == "build":
            p["buildings"][task["key"]] = task["level"]
        elif task["kind"] == "ship":
            produced = self._produced_ships(p["owner_id"], task["key"], task["amount"])
            p["ships"][task["key"]] = p["ships"].get(task["key"], 0) + produced
        else:
            player = self.data["players"][p["owner_id"]]
            old_level = player["research"].get(task["key"], 0)
            new_level = max(old_level, task["level"])
            player["research"][task["key"]] = new_level
            if task["key"] == "multiplication":
                grown = self._multiply_existing_fleet(p["owner_id"], old_level, new_level)
            # Fixed at purchase, paid once at completion, never from Swarm currency.
            refund = int(task.get("crystal_refund", 0))
            p["resources"]["crystal"] = min(MAX_RESOURCE, p["resources"]["crystal"] + refund)
        construction_refund = task.get("construction_refund", {}) if task["kind"] in ("build", "ship") else {}
        received = {}
        for resource in RESOURCES:
            refund = max(0, int(construction_refund.get(resource, 0)))
            before = p["resources"][resource]
            p["resources"][resource] = min(MAX_RESOURCE, before + refund)
            received[resource] = int(p["resources"][resource] - before)
        if p["owner_type"] == "player":
            if task["kind"] == "build" and task["key"] in BUILDINGS:
                onboarding.record(self._player(p["owner_id"]), "first_building")
            names = self._specs(p["owner_id"], {"build": "buildings", "ship": "ships", "research": "research"}[task["kind"]])
            self._report(p["owner_id"], t('Ukończono projekt'), t('{0}: {1}').format(p['name'], names[task['key']][0]) + (t(' ×{0}.').format(produced) if task["kind"] == "ship" else t(', poziom {0}.').format(task['level'])))
            if task["kind"] == "research" and task["key"] in UNIQUE_RESEARCH.get(self._race_id(p["owner_id"]), {}):
                effect = research_effect_text(task["key"], new_level)
                if task["key"] == "multiplication":
                    effect += t('. Przybyło {0} statków w koloniach i podróży.').format(grown)
                self._report(p["owner_id"], names[task["key"]][0], effect + t(' Działa w całym imperium.'), art_key(self._race_id(p["owner_id"]), task["key"]))
            if any(received.values()):
                self._report(p["owner_id"], t('Recykling'), t('{0}: odzyskano {1} metalu, {2} kryształów i {3} paliwa.').format(p['name'], received['metal'], received['crystal'], received['fuel']), art_key("automatons", "recycling"))
            if task.get("crystal_refund", 0):
                self._report(p["owner_id"], t('Archiwum Synaps'), t('{0}: ukończone badanie zwróciło {1} zwykłych kryształów.').format(p['name'], task['crystal_refund']), art_key(self._race_id(p["owner_id"]), "synapse_archive"))

    @staticmethod
    def _credentials(name, password):
        if not isinstance(name, str) or not isinstance(password, str):
            raise GameError(t('Podaj nazwę i hasło.'))
        name = unicodedata.normalize("NFKC", name.strip())
        if not 3 <= len(name) <= 20 or not all(c.isalnum() or c in " _-" for c in name):
            raise GameError(t('Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -.'))
        if not 8 <= len(password) <= 128:
            raise GameError(t('Hasło musi mieć 8–128 znaków.'))
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

    @atomic_mutation
    def register(self, name, password, invite=""):
        # Older clients may still send an invitation; registration is now open.
        # The legacy field is deliberately ignored and never stored or returned.
        name, password = self._credentials(name, password)
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(password, salt)
        with self.lock:
            if self.db.execute("SELECT 1 FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone():
                raise GameError(t('Ta nazwa jest już zajęta.'), 409)
            if self.max_players and len(self.data["players"]) >= self.max_players:
                raise GameError(t('Ten sektor osiągnął ustawiony przez gospodarza limit {0} kont. Jeśli masz już konto, wybierz Zaloguj.').format(self.max_players), 409)
            empty = [p for p in self.data["planets"].values() if p["owner_type"] == "empty" and self._galaxy_id(p) == "g1"]
            if not empty:
                raise GameError(t('W galaktyce nie ma już wolnej planety startowej.'), 409)
            occupied = [p for p in self.data["planets"].values() if p["owner_type"] != "empty"]
            p = max(empty, key=lambda candidate: (min((self._distance(candidate, q) for q in occupied), default=0), -candidate["slot"]))
            pid = ident("u")
            player = {"id": pid, "name": name, "race_id": "", "swarm_crystals": 0, "skill_nodes": [], "home_id": p["id"], "protected_until": self.now + 86400, "research": dict.fromkeys(RESEARCH, 0), "reports": [], "requests": {}}
            p["owner_type"], p["owner_id"] = "player", pid
            p["buildings"] = dict.fromkeys(BUILDINGS, 1)
            p["resources"] = {"metal": 4000.0, "crystal": 2600.0, "fuel": 1400.0}
            p["ships"] = {**blank_ships(), "scout": 2, "cargo": 1, "colonizer": 1, "frigate": 3}
            self.data["players"][pid] = player
            self._report(pid, t('Witaj w Alien Colonies'), t(WELCOME_REPORT_TEXT))
            self.db.execute("INSERT INTO accounts VALUES(?,?,?,?)", (pid, name.casefold(), salt, password_hash))
            token = self._session(pid)
            self._save()
            return {"ok": True, "token": token, "state": self.state(pid), "message": t('Założono imperium.')}

    @atomic_mutation
    def login(self, name, password):
        name, password = self._credentials(name, password)
        with self.lock:
            row = self.db.execute("SELECT id,salt,password_hash FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone()
            salt = row[1] if row else "00" * 16
            candidate = self._password_hash(password, salt)
            if not row or not hmac.compare_digest(candidate, row[2]):
                raise GameError(t('Nieprawidłowa nazwa lub hasło.'), 401)
            token = self._session(row[0])
            return {"ok": True, "token": token, "state": self.state(row[0]), "message": t('Witaj ponownie.')}

    def authenticate(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise GameError(t('Zaloguj się ponownie.'), 401)
        with self.lock:
            row = self.db.execute("SELECT player_id FROM sessions WHERE token_hash=? AND expires>?", (hashlib.sha256(token.encode()).hexdigest(), self.now)).fetchone()
            if not row:
                raise GameError(t('Sesja wygasła. Zaloguj się ponownie.'), 401)
            return row[0]

    @atomic_mutation
    def logout(self, token):
        with self.lock:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def _player(self, player_id):
        player = self.data["players"].get(player_id)
        if not player:
            raise GameError(t('Nie znaleziono gracza.'), 401)
        return player

    def _owned(self, player_id, planet_id=None):
        player = self._player(player_id)
        if planet_id is None:
            planet_id = player["home_id"]
        if not isinstance(planet_id, str):
            raise GameError(t('Nieprawidłowa planeta.'))
        p = self.data["planets"].get(planet_id)
        if not p or p["owner_id"] != player_id or p["owner_type"] != "player":
            raise GameError(t('Ta planeta nie należy do ciebie.'), 403)
        return p

    def _report(self, player_id, title, text, art_key="", swarm_crystals=0):
        player = self.data["players"].get(player_id)
        if player:
            player["reports"].insert(0, {"id": ident("r"), "at": self.now, "title": render_text(store_text(title), "pl"), "text": render_text(store_text(text), "pl"), "art_key": art_key, "swarm_crystals": swarm_crystals, "i18n": {"title": store_text(t(title)), "text": store_text(text)}})
            del player["reports"][80:]

    def _local_distance(self, a, b):
        # Do not index an array by a numeric ID: snapshots may reorder systems.
        by_id = {system["id"]: system for system in self.data["systems"]}
        sa, sb = by_id[a["system_id"]], by_id[b["system_id"]]
        return math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]) + abs(a["slot"] - b["slot"]) * 0.08 + 0.1

    def _distance(self, a, b):
        return self._local_distance(a, b) + separation(self._galaxy_id(a), self._galaxy_id(b)) * 1_000_000

    def _flight_numbers(self, origin, target, fleet, propulsion=0):
        distance = self._local_distance(origin, target)
        specs = self._specs(origin["owner_id"], "ships")
        slowest = min(specs[k][8] for k, n in fleet.items() if n)
        antigravity = 1 + .2 * self._racial_research_level(origin["owner_id"], "antigravity")
        speed_factor = slowest * (1 + propulsion * .15) * antigravity * self.speed
        local_fuel_factor = 1 - self._building_effects(origin).get("fleet_fuel_reduction", 0)
        mass = sum(specs[k][7] * n for k, n in fleet.items() if n)
        gap = separation(self._galaxy_id(origin), self._galaxy_id(target))
        if gap:
            seconds = max(8, math.ceil((JUMP_SECONDS_PER_MLY * gap + 100 + distance * 130) / speed_factor))
            # A non-discountable jump activation cost prevents a single cheap
            # scout from opening a practically free intergalactic route.
            fuel = math.ceil(gap * (JUMP_BASE_FUEL + JUMP_FUEL_PER_MASS * mass * local_fuel_factor))
        else:
            seconds = max(8, math.ceil((100 + distance * 130) / speed_factor))
            fuel = max(1, math.ceil(mass * (1 + distance) * 2 * local_fuel_factor))
        return seconds, fuel

    def _fleet_quote(self, player_id, payload, *, require_affordable=True):
        p = self._owned(player_id, payload.get("planet_id"))
        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or target_id not in self.data["planets"]:
            raise GameError(t('Wybierz planetę docelową.'))
        target = self.data["planets"][target_id]
        if target_id == p["id"]:
            raise GameError(t('Wybierz inną planetę.'))
        mission = payload.get("mission")
        if mission not in ("scout", "transport", "colonize", "attack"):
            raise GameError(t('Nieznany rodzaj misji.'))
        specs = self._specs(player_id, "ships")
        race_id = self._race_id(player_id)
        ships = counts(payload.get("ships"), specs, t('Liczba statków'), 10_000)
        cargo = counts(payload.get("cargo", {}), RESOURCES, t('Ładunek'), MAX_RESOURCE)
        if not sum(ships.values()):
            raise GameError(t('Wybierz przynajmniej jeden statek.'))
        if any(n > p["ships"].get(k, 0) for k, n in ships.items()):
            raise GameError(t('Nie masz tylu statków na tej planecie.'))
        if len([f for f in self.data["fleets"].values() if f["owner_id"] == player_id]) >= 8:
            raise GameError(t('Możesz prowadzić najwyżej 8 misji naraz.'), 409)
        if mission == "scout" and ships["scout"] < 1:
            raise GameError(t('Wymagany okręt do zwiadu: {0}.').format(specs['scout'][0]) if race_id else t('Zwiad wymaga zwiadowcy.'))
        if mission == "transport" and target["owner_id"] != player_id:
            raise GameError(t('Transport jest dostępny między twoimi planetami.'))
        if mission == "colonize":
            if ships["colonizer"] < 1 or target["owner_type"] != "empty":
                raise GameError(t('Kolonizacja wymaga okrętu {0} i wolnej planety.').format(specs['colonizer'][0]) if race_id else t('Kolonizacja wymaga kolonizatora i wolnej planety.'))
            colonies = sum(q["owner_id"] == player_id for q in self.data["planets"].values())
            pending = sum(f["owner_id"] == player_id and f["mission"] == "colonize" and f["status"] == "outbound" for f in self.data["fleets"].values())
            if colonies + pending >= MAX_COLONIES:
                raise GameError(t('Limit to {0} kolonii, wliczając wysłane ekspedycje.').format(MAX_COLONIES), 409)
        if mission == "attack":
            if not any(ships.get(key, 0) for key in ("frigate", "cruiser", "interceptor", "siege")):
                raise GameError(t('Wymagany okręt do ataku: {0} lub {1}; możesz też użyć jednostki {2} albo {3}.').format(specs['frigate'][0], specs['cruiser'][0], specs['interceptor'][0], specs['siege'][0]))
            if target["owner_type"] == "empty" or target["owner_id"] == player_id:
                raise GameError(t('Możesz atakować obce kolonie lub innych graczy.'))
            if target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now:
                raise GameError(t('Ten gracz jest objęty ochroną startową.'), 403)
        if mission not in ("transport", "colonize") and sum(cargo.values()):
            raise GameError(t('Ładunek można zabrać na transport lub kolonizację.'))
        capacity = fleet_capacity(specs, ships)
        if sum(cargo.values()) > capacity:
            raise GameError(t('Ładunek przekracza pojemność {0}.').format(capacity))
        seconds, fuel = self._flight_numbers(p, target, ships, self._player(player_id)["research"]["propulsion"])
        effects = self._building_effects(p)
        if mission == "scout":
            seconds = max(8, math.ceil(seconds * (1 - effects.get("scout_time_reduction", 0))))
        cost = dict(cargo)
        cost["fuel"] += fuel
        if require_affordable and not affordable(p, cost):
            raise GameError(t('Brakuje zapasów. Lot wymaga {0} paliwa, oprócz zabieranego ładunku.').format(fuel))
        return p, target, ships, cargo, cost, seconds, fuel, capacity

    def preview(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError(t('Nieprawidłowe dane misji.'))
            p, target, ships, cargo, cost, seconds, fuel, capacity = self._fleet_quote(player_id, payload, require_affordable=payload.get("allow_unaffordable") is not True)
            result = {"ok": True, "fuel_cost": fuel, "seconds": seconds, "capacity": capacity, "message": t('Paliwo obejmuje podróż w obie strony.')}
            result["route"] = self._route_details(p, target)
            result["affordable"] = affordable(p, cost)
            result["shortfall"] = {k: max(0, math.ceil(v - p["resources"][k])) for k, v in cost.items()}
            if result["route"]["intergalactic"]:
                result["message"] += " " + t('Lot między galaktykami: ogromny koszt paliwa. Cała kwota jest pobierana przy starcie; powrót nie wymaga dopłaty.')
            if payload.get("mission") == "colonize":
                result["colony_start_level"] = self._colony_start_level(player_id, self._building_effects(p))
                if result["colony_start_level"] > 1:
                    result["message"] += t(' Nowa kolonia: cztery budynki gospodarcze na poziomie {0}.').format(result['colony_start_level'])
            elif payload.get("mission") == "attack" and target["owner_id"] == "khar":
                stock = int(target.get("swarm_crystals", 0))
                result["message"] += t(' Silna obrona Roju — sprawdź zwiad i skoordynuj naloty.')
                result["message"] += t(' Kryształy w gnieździe: {0}.').format(stock) if stock else t(' Brak kryształów do zdobycia.')
            return result

    def _colony_start_level(self, owner_id, effects):
        # Only new dispatches record this bonus. Legacy fuel-discount snapshots
        # never turn into free building levels, even if the nursery was upgraded.
        bonus = effects.get("colony_start_building_bonus", 0) if self._race_id(owner_id) == "symbionts" else 0
        return 1 + max(0, min(5, int(bonus)))

    @staticmethod
    def _regeneration_fraction(rules, *, defense_effects=None):
        # Only the attacked planet's current Grove can heal its stationed ships.
        # Travelling fleets retain innate/skill regeneration, never a Grove bonus.
        bonus = (defense_effects or {}).get("renewal_fraction", 0)
        return max(0.0, min(1.0, rules["regeneration_fraction"] + bonus))

    def _catalog(self, player_id, p):
        player = self._player(player_id)
        result = {"buildings": [], "research": [], "ships": []}
        race_id = self._race_id(player_id)
        rules = self._rules(player_id)
        effects = self._building_effects(p)
        for group in ("buildings", "research", "ships"):
            for key, spec in self._specs(player_id, group).items():
                level = (p["buildings"] if group == "buildings" else player["research"] if group == "research" else p["ships"]).get(key, 0)
                unique = (UNIQUE_BUILDINGS if group == "buildings" else UNIQUE_RESEARCH).get(race_id, {}).get(key) if group in ("buildings", "research") else None
                max_level = 5 if unique else 12
                requirements = self._entry_requirements(player_id, p, group, key)
                cost = scaled_cost(spec[2], level if group != "ships" else 0)
                duration_bonus = self._bonuses(player_id).get("research_speed" if group == "research" else "build_speed", 0)
                building_reduction = (effects.get("building_time_reduction", 0) if group == "buildings" else
                                      effects.get("ship_time_reduction", 0) if group == "ships" else 0)
                seconds = max(1, math.ceil(spec[3] * (1.3 ** level if group != "ships" else 1) / self.speed / (1.0 + duration_bonus) * (1 - building_reduction)))
                reason = ""
                if p["queue"]:
                    reason = t('Planeta realizuje już projekt.')
                elif group != "ships" and level >= max_level:
                    reason = t('Osiągnięto maksymalny poziom {0}.').format(max_level)
                elif group == "ships" and key in ("interceptor", "siege", "freighter") and not race_id:
                    reason = t('Wybierz rasę imperium, aby odblokować zaawansowane okręty.')
                elif any(not requirement["met"] for requirement in requirements):
                    reason = t('Wymaga: ') + join_text(", ", (t("{0} (poziom {1})").format(requirement["name"], requirement["level"]) for requirement in requirements if not requirement['met'])) + "."
                elif group == "research" and any(q["queue"] and q["queue"][0]["kind"] == "research" for q in self.data["planets"].values() if q["owner_id"] == player_id):
                    reason = t('Badanie trwa na innej planecie.')
                elif not affordable(p, cost):
                    reason = t('Brakuje surowców.')
                item = {"key": key, "name": spec[0], "description": spec[1], "level": level, "cost": cost, "seconds": seconds, "enabled": not reason, "reason": reason,
                        "requirements": requirements}
                if group != "ships":
                    item["max_level"] = max_level
                role = "scout" if key == "propulsion" else "weapon" if key == "weapons" else key
                item["art_key"] = art_key(race_id, role)
                item["race_id"] = race_id
                if unique:
                    effect_text = unique_effect_text if group == "buildings" else research_effect_text
                    item.update(unique=True, max_level=5, requirements=requirements,
                                effect_current=effect_text(key, level),
                                effect_next=effect_text(key, level + 1) if level < 5 else t('Maksymalny poziom.'))
                if group in ("buildings", "ships"):
                    item["construction_refund_rate"] = self._racial_research_level(player_id, "recycling") / 20
                if group == "ships":
                    siege_multiplier = SHIP_TRAITS.get(key, {}).get("swarm_attack_multiplier", 1.0)
                    item.update(count=level, attack=spec[4], hull=spec[5], capacity=spec[6],
                                fuel=spec[7], speed=spec[8], role=key,
                                category="combat" if key in ("frigate", "cruiser", "interceptor", "siege") else "utility",
                                effective_fuel=round(spec[7] * (1 - effects.get("fleet_fuel_reduction", 0)), 6),
                                swarm_attack_multiplier=siege_multiplier,
                                effective_swarm_attack=spec[4] * (1 + player["research"]["weapons"] * .15) * siege_multiplier * (1 + self._bonuses(player_id).get("swarm_damage", 0)),
                                ship_time_reduction=effects.get("ship_time_reduction", 0),
                                effective_attack=spec[4] * (1 + player["research"]["weapons"] * .15),
                                effective_speed=spec[8] * (1 + player["research"]["propulsion"] * .15) * (1 + .2 * self._racial_research_level(player_id, "antigravity")),
                                production_multiplier=float(self._fleet_multiplier(player_id)),
                                first_volley_multiplier=rules["first_volley_multiplier"],
                                regeneration_fraction=self._regeneration_fraction(rules),
                                defense_regeneration_fraction=self._regeneration_fraction(rules, defense_effects=effects),
                                defense_regeneration_bonus=effects.get("renewal_fraction", 0),
                                damage_reduction=rules["damage_reduction"],
                                batch_time_reduction_per_extra=effects.get("batch_time_reduction_per_extra", 0),
                                batch_time_reduction_cap=.30)
                elif group == "research":
                    item["crystal_refund"] = math.floor(round(cost["crystal"] * effects.get("research_crystal_refund", 0), 6))
                elif group == "buildings":
                    if key in rules["energy_use_per_level"]:
                        resource, base, rate = {"metal_mine": ("metal", 90, 450),
                                                "crystal_mine": ("crystal", 60, 330),
                                                "refinery": ("fuel", 30, 180)}[key]
                        multiplier = (rules["production_multipliers"][resource] * (1 + effects.get("production_all", 0))
                                      * (1 + effects.get("production_" + resource, 0)))
                        item.update(production_resource=resource,
                                    production_per_level=rate * multiplier * self.speed,
                                    base_production=base * multiplier * self.speed,
                                    energy_per_level=round(rules["energy_use_per_level"][key] * (1 - effects.get("mining_energy_reduction", 0)), 6))
                    elif key == "power_plant":
                        item["energy_supply_per_level"] = rules["energy_supply_per_level"]
                        energy_text = format_number(rules["energy_supply_per_level"])
                        item["description"] = t('Zapewnia {0} energii na poziom, z uwzględnieniem umiejętności. Energia zasila wydobycie.').format(energy_text)
                result[group].append(item)
        return result

    @atomic_mutation
    def action(self, player_id, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise GameError(t('Nieprawidłowe polecenie.'))
            p = self._owned(player_id, payload.get("planet_id"))
            player = self._player(player_id)
            request_id = payload.get("request_id")
            if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 100):
                raise GameError(t('Nieprawidłowy identyfikator polecenia.'))
            try:
                fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                raise GameError(t('Polecenie zawiera nieprawidłowe wartości.'))
            if request_id in player["requests"]:
                prior = player["requests"][request_id]
                if prior["fingerprint"] != fingerprint:
                    raise GameError(t('Ten identyfikator został użyty dla innego polecenia.'), 409)
                return {"ok": True, "state": self.state(player_id, p["id"]), "message": render_text(prior.get("message_i18n", prior["message"]))}
            kind = payload.get("type")
            if kind == "choose_race":
                race_id = payload.get("race_id")
                if not isinstance(race_id, str) or race_id not in RACES:
                    raise GameError(t('Wybierz jedną z trzech dostępnych ras.'))
                reason = self._race_choice_reason(player_id)
                if reason:
                    raise GameError(reason, 409)
                player["race_id"] = race_id
                onboarding.record(player, "race_chosen")
                self._ensure_racial_research(player)
                player["skill_nodes"] = skill_tree.unlocked_for(race_id, [])
                player.setdefault("swarm_crystals", 0)
                for owned in self.data["planets"].values():
                    if owned["owner_id"] == player_id:
                        self._ensure_race_buildings(owned)
                message = t('Wybrano rasę: {0}. To stały wybór tego imperium.').format(t(RACES[race_id]['name']))
                self._report(player_id, t('Narodziny cywilizacji'), message + " " + t(RACES[race_id]["trait"]) + " " + t(RACES[race_id]["tradeoff"]))
            elif kind == "unlock_skill":
                try:
                    quote = skill_tree.quote_unlock(self._race_id(player_id), player.get("skill_nodes", []),
                                                    payload.get("node_id"), player.get("swarm_crystals", 0))
                except (ValueError, TypeError) as exc:
                    raise GameError(str(exc), 409) from None
                player["skill_nodes"] = quote["unlocks"]
                player["swarm_crystals"] = quote["balance_after"]
                if quote["cost"] > 0:
                    onboarding.record(player, "first_skill")
                node = next(node for node in skill_tree.graph()["nodes"] if node["id"] == quote["node_id"])
                message = t('Rozwinięto umiejętność: {0}. Wydano {1} Kryształów Roju.').format(node['name'], quote['cost'])
                self._report(player_id, t('Nowa umiejętność'), message, node.get("art_key", ""))
            elif kind == "fleet":
                p, target, ships, cargo, cost, seconds, fuel, _ = self._fleet_quote(player_id, payload)
                spend(p, cost)
                for key, n in ships.items():
                    p["ships"][key] = p["ships"].get(key, 0) - n
                mission = payload["mission"]
                if mission == "attack" and target["owner_type"] == "player":
                    player["protected_until"] = min(player["protected_until"], self.now)
                fleet = {"id": ident("f"), "owner_id": player_id, "race_id": self._race_id(player_id), "origin_id": p["id"], "target_id": target["id"], "mission": mission, "status": "outbound", "ships": ships, "cargo": cargo, "swarm_crystals": 0, "started_at": self.now, "seconds": seconds, "arrives_at": self.now + seconds}
                fleet["route"] = self._route_details(p, target)
                fleet["fuel_paid"] = fuel
                fleet["building_effects"] = self._building_effects(p)
                fleet["building_effects"].pop("renewal_fraction", None)
                self.data["fleets"][fleet["id"]] = fleet
                if mission == "attack" and target["owner_type"] == "player":
                    self._report(target["owner_id"], t('Nadciąga wroga flota'), t('Imperium {0} wysłało atak z {1} na {2}. Do celu: {3} s.').format(player['name'], p['name'], target['name'], seconds))
                message = t('Flota wyruszyła: {0} s, koszt {1} paliwa za podróż w obie strony.').format(seconds, fuel)
            elif kind in ("build", "research", "ship"):
                group = {"build": "buildings", "research": "research", "ship": "ships"}[kind]
                key = payload.get("key")
                entry = next((x for x in self._catalog(player_id, p)[group] if x["key"] == key), None)
                if entry is None:
                    raise GameError(t('Nieznany projekt.'))
                if not entry["enabled"]:
                    raise GameError(entry["reason"], 409)
                amount = integer(payload.get("amount", 1), t('Liczba statków'), 1, 20) if kind == "ship" else 1
                cost = {k: v * amount for k, v in entry["cost"].items()}
                if not affordable(p, cost):
                    raise GameError(t('Brakuje surowców na całą partię.'), 409)
                spend(p, cost)
                reduction = min(entry.get("batch_time_reduction_cap", 0), entry.get("batch_time_reduction_per_extra", 0) * (amount - 1))
                duration = max(1, math.ceil(entry["seconds"] * amount * (1 - reduction)))
                p["queue"].append({"id": ident("q"), "kind": kind, "key": key, "amount": amount,
                                   "level": entry["level"] + 1, "started_at": self.now,
                                   "seconds": duration, "ends_at": self.now + duration,
                                   "crystal_refund": entry.get("crystal_refund", 0),
                                   "construction_refund": {k: v * self._racial_research_level(player_id, "recycling") // 20 for k, v in cost.items()} if kind in ("build", "ship") else {}})
                message = t('Rozpoczęto projekt.')
            else:
                raise GameError(t('Nieznane polecenie.'))
            if request_id:
                player["requests"][request_id] = {"fingerprint": fingerprint, "message": render_text(store_text(message), "pl"), "message_i18n": store_text(message)}
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
        f["started_at"] = self.now

    def _land(self, p, f):
        # Settled flights cannot be credited twice, including stale event references.
        if f["id"] not in self.data["fleets"]:
            return False
        # An eradicated outpost cannot hand its returning Swarm ships to a player.
        if p["owner_id"] != f["owner_id"]:
            self._return(f)
            return False
        for key, n in f["ships"].items():
            p["ships"][key] = p["ships"].get(key, 0) + n
        for k, v in f["cargo"].items():
            p["resources"][k] = min(MAX_RESOURCE, p["resources"][k] + v)
        crystals = int(f.get("swarm_crystals", 0))
        player = self.data["players"].get(f["owner_id"])
        if player and crystals:
            player["swarm_crystals"] = player.get("swarm_crystals", 0) + crystals
            if crystals > 0 and f["status"] == "returning":
                onboarding.record(player, "swarm_crystals")
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
                reward = t(' Przywieziono {0} Kryształów Roju — możesz wydać je w kole umiejętności.').format(crystals) if crystals else ""
                self._report(owner, t('Flota wróciła'), t('Statki wróciły na {0}. Ładunek został rozładowany.').format(p['name']) + reward,
                             "swarm/crystal" if crystals else "", crystals)
            return
        mission = f["mission"]
        if mission == "scout":
            owner_name = t('Wolna planeta') if target["owner_type"] == "empty" else t(self.data["alien"]["name"]) if target["owner_type"] == "alien" else self._player(target["owner_id"])["name"]
            stocks = join_text(", ", (t('{0}: {1}').format(name, int(target['resources'][key])) for key, name in zip(RESOURCES, (t('metal'), t('kryształy'), t('paliwo')))))
            target_specs = self._specs(target["owner_id"], "ships")
            ships = join_text(", ", (t('{0} ×{1}').format(target_specs[k][0], n) for k, n in target['ships'].items() if n)) or t('brak statków')
            detail = ""
            if target["owner_id"] == "khar":
                if owner in self.data["players"]:
                    onboarding.record(self._player(owner), "swarm_scout")
                stage = swarm.public_planet(target)
                structures = join_text(", ", (t('{0} {1}').format(t(swarm.BUILDINGS[key][0]), level) for key, level in target['buildings'].items() if level))
                detail = t(' {0}. Kryształy Roju: {1}. Budynki Roju: {2}. Technologia bojowa: {3}. Odnowa: 1 kryształ na 18 godzin po odbudowie obrony. Silny cel — skoordynuj naloty.').format(stage['swarm_kind_name'], int(target.get('swarm_crystals', 0)), structures, self._swarm_weapon_level(target))
            self._report(owner, t('Raport zwiadu'), t('{0} — {1}. Zapasy: {2}. Flota: {3}.').format(target['name'], owner_name, stocks, ships) + detail,
                         "swarm/colony" if target["owner_id"] == "khar" else "")
            self._return(f)
        elif mission == "transport":
            if target["owner_id"] == owner:
                for k, v in f["cargo"].items():
                    target["resources"][k] = min(MAX_RESOURCE, target["resources"][k] + v)
                f["cargo"] = dict.fromkeys(RESOURCES, 0)
                self._report(owner, t('Dostarczono transport'), t('Zapasy dotarły na {0}. Statki wracają.').format(target['name']))
            else:
                self._report(owner, t('Transport zawrócił'), t('Planeta docelowa zmieniła właściciela.'))
            self._return(f)
        elif mission == "colonize":
            count = sum(p["owner_id"] == owner for p in self.data["planets"].values())
            limit = swarm.MAX_COLONIES if owner == "khar" else MAX_COLONIES
            if target["owner_type"] == "empty" and count < limit and f["ships"]["colonizer"] > 0:
                target["owner_type"] = "alien" if owner == "khar" else "player"
                target["owner_id"] = owner
                target["buildings"] = dict.fromkeys(BUILDINGS, 0)
                self._ensure_race_buildings(target)
                starting_level = self._colony_start_level(owner, f.get("building_effects", {}))
                for k in ("metal_mine", "crystal_mine", "refinery", "power_plant"):
                    target["buildings"][k] = starting_level
                target["resources"] = {"metal": 450.0, "crystal": 250.0, "fuel": 150.0}
                if owner == "khar":
                    # The seed hull pays for the nest. Its escort consists of real ships
                    # removed from the origin, and never appears for free on arrival.
                    swarm.seed(target, self.now, hive=False)
                f["ships"]["colonizer"] -= 1
                self._land(target, f)
                if owner in self.data["players"] and count >= 1:
                    onboarding.record(self._player(owner), "second_colony")
                nursery_text = t(' Zarodnia Pionierów: cztery budynki gospodarcze zaczynają na poziomie {0}.').format(starting_level) if starting_level > 1 else ""
                self._report(owner, t('Nowa kolonia'), t('Założono kolonię {0}. Kolonizator rozebrano na bazę; pozostałe statki i zapasy zostały na miejscu.').format(target['name']) + nursery_text)
                if owner == "khar":
                    for player_id in self.data["players"]:
                        self._report(player_id, t('Rój Khar rozszerza granice'), t('Zarodnia dotarła na {0}. Rój zakłada nowe gniazdo i umacnia jego obronę.').format(target['name']), "swarm/colony")
            else:
                self._report(owner, t('Kolonizacja przerwana'), t('{0} nie jest już dostępna lub osiągnięto limit kolonii. Flota wraca.').format(target['name']))
                self._return(f)
        else:
            if target["owner_type"] == "empty" or target["owner_id"] == owner or (target["owner_type"] == "player" and self._player(target["owner_id"])["protected_until"] > self.now) or (owner == "khar" and not f.get("swarm_raid", False) and target["owner_type"] == "player" and any(q["owner_type"] == "empty" for q in self.data["planets"].values())):
                self._report(owner, t('Atak odwołany'), t('Cel nie może zostać zaatakowany. Flota wraca.'))
                self._return(f)
            else:
                self._battle(f, target)

    @staticmethod
    def _power(fleet, weapons, specs=None, multiplier=1.0, *, type_multipliers=None):
        specs = SHIPS if specs is None else specs
        factors = type_multipliers or {}
        return sum(specs[k][4] * n * factors.get(k, 1.0) for k, n in fleet.items() if n) * (1 + weapons * .15) * multiplier

    @staticmethod
    def _damage(fleet, damage, wounds, specs=None, damage_reduction=0.0):
        # Small ships absorb damage first; surviving wounds persist between rounds.
        specs = SHIPS if specs is None else specs
        damage *= 1.0 - damage_reduction
        for key in sorted(specs, key=lambda k: (specs[k][5], k)):
            if fleet.get(key, 0) <= 0:
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
        rare_loot_eligible = (defender == "khar"
                              and defending_before.get("frigate", 0) + defending_before.get("cruiser", 0) > 0
                              and (not target.get("swarm_loot_sealed", False) or self._swarm_ready(target)))
        aw = int(f.get("swarm_weapon_level", 0)) if attacker == "khar" else self._player(attacker)["research"]["weapons"]
        dw = self._swarm_weapon_level(target) if defender == "khar" else self._player(defender)["research"]["weapons"]
        specs_a, specs_d = self._specs(attacker, "ships"), self._specs(defender, "ships")
        rules_a, rules_d = self._rules(attacker), self._rules(defender)
        # An older already travelling fleet has no retroactive building bonus.
        effects_a = f.get("building_effects", {})
        effects_d = self._building_effects(target)
        # Ignore renewal_fraction even if a legacy fleet saved it at departure.
        regeneration_a = self._regeneration_fraction(rules_a)
        regeneration_d = self._regeneration_fraction(rules_d, defense_effects=effects_d)
        wounds_a, wounds_d = {}, {}
        anti_swarm_a = 1.0 + (self._bonuses(attacker).get("swarm_damage", 0) if defender == "khar" else 0)
        anti_swarm_d = 1.0 + (self._bonuses(defender).get("swarm_damage", 0) if attacker == "khar" else 0)
        siege_factors = {key: meta.get("swarm_attack_multiplier", 1.0) for key, meta in SHIP_TRAITS.items()} if defender == "khar" else {}
        rounds = 0
        for _ in range(6):
            if not sum(f["ships"].values()) or not sum(target["ships"].values()):
                break
            rounds += 1
            attack = self._power(f["ships"], aw, specs_a, (rules_a["first_volley_multiplier"] if rounds == 1 else 1.0) * anti_swarm_a, type_multipliers=siege_factors)
            defense = self._power(target["ships"], dw, specs_d, (rules_d["first_volley_multiplier"] * (1 + effects_d.get("defense_first_volley", 0)) if rounds == 1 else 1.0) * anti_swarm_d)
            self._damage(target["ships"], attack, wounds_d, specs_d, rules_d["damage_reduction"])
            self._damage(f["ships"], defense, wounds_a, specs_a, rules_a["damage_reduction"])
            self._regenerate(f["ships"], wounds_a, regeneration_a)
            self._regenerate(target["ships"], wounds_d, regeneration_d)
        victory = sum(target["ships"].values()) == 0 and sum(f["ships"].values()) > 0
        capacity = fleet_capacity(specs_a, f["ships"])
        f["cargo"] = dict.fromkeys(RESOURCES, 0)
        f["swarm_crystals"] = 0
        recovered_metal = 0
        eradicated = False
        if victory:
            if defender == "khar" and attacker in self.data["players"]:
                stage = swarm.kind(target)
                quota = math.floor(swarm.RAID_CRYSTALS[stage] * (1.0 + self._bonuses(attacker).get("swarm_loot", 0)))
                crystals = min(int(target.get("swarm_crystals", 0)), quota, capacity) if rare_loot_eligible else 0
                target["swarm_crystals"] = max(0.0, target.get("swarm_crystals", 0) - crystals)
                f["swarm_crystals"] = crystals
                capacity -= crystals
                # Preserve attrition between cooperating players' separate raids.
                # Only victory seals the reserve: partial losses never do. The
                # remainder cannot be collected by a free zero-round follow-up
                # or by repeatedly killing the first rebuilding ship.
                target["swarm_loot_sealed"] = True
                # Defeating the stationed fleet never cancels paid reconstruction,
                # damages the shipyard or renews a suppression timer. An empty
                # nest cannot keep producing rare loot while its defense is pinned.
                target["swarm_suppressed_until"] = 0
            destroyed_metal = sum(specs_d[key][2][0] * (count - target["ships"].get(key, 0)) for key, count in defending_before.items() if count)
            recovered_metal = min(capacity, math.floor(round(destroyed_metal * effects_a.get("wreck_recovery_fraction", 0), 6)))
            f["cargo"]["metal"] = recovered_metal
            capacity -= recovered_metal
            available = self._lootable_resources(target)
            total = sum(available.values())
            if total:
                for k, v in available.items():
                    n = min(v, math.floor(capacity * v / total)) if total > capacity else v
                    f["cargo"][k] += n
                    target["resources"][k] -= n
        if eradicated:
            target.update(owner_id="", owner_type="empty", resources=dict.fromkeys(RESOURCES, 0.0),
                          buildings=dict.fromkeys(BUILDINGS, 0), ships=blank_ships(), queue=[])
            for key in tuple(target):
                if key.startswith("swarm_"):
                    del target[key]
        lost_a = join_text(", ", (t('{0} ×{1}').format(specs_a[k][0], n - f['ships'][k]) for k, n in attacking_before.items() if n > f['ships'][k])) or t('brak')
        lost_d = join_text(", ", (t('{0} ×{1}').format(specs_d[k][0], n - target['ships'][k]) for k, n in defending_before.items() if n > target['ships'][k])) or t('brak')
        outcome = t('Zwycięstwo') if victory else t('Klęska') if sum(f["ships"].values()) == 0 else t('Nierozstrzygnięta bitwa — odwrót')
        summary = t('{0}: {1}. Rundy: {2}. Straty atakującego: {3}. Straty obrońcy: {4}. Zdobycz: metal {5}, kryształy {6}, paliwo {7}. ').format(target['name'], outcome, rounds, lost_a, lost_d, f['cargo']['metal'], f['cargo']['crystal'], f['cargo']['fuel'])
        if recovered_metal:
            summary += t(' Recykler Wraków odzyskał {0} metalu; jest w ładowni i zostanie rozładowany po powrocie.').format(recovered_metal)
        if effects_d.get("defense_first_volley", 0):
            summary += t(' Cytadela Magnetyczna: pierwsza salwa obrońcy +{0}%.').format(round(effects_d['defense_first_volley'] * 100))
        if effects_d.get("renewal_fraction", 0):
            summary += t(' Gaj Odnowy — regeneracja obrony planety +{0} pkt proc.').format(round(effects_d['renewal_fraction'] * 100))
        if defender == "khar":
            if attacking_before.get("siege", 0):
                summary += t(' Okręty oblężnicze: atak przeciw obronie Roju +50%.')
            summary += t(' Kryształy Roju: {0} w ładowni; trafią do koła po powrocie floty.').format(f['swarm_crystals'])
            if eradicated:
                summary += t(' Przyczółek został zniszczony. Planeta jest wolna i można ją skolonizować.')
            elif victory:
                summary += t(' Obrona została przełamana. Gniazdo zachowuje budynki i odbudowuje flotę. Odnowa kryształów czeka na odbudowę obrony.')
        else:
            summary += t(' Budynki i własność planety pozostają bez zmian.')
        for label, owner_id, regeneration in ((t('Atakujący'), attacker, regeneration_a), (t('Obrońca'), defender, regeneration_d)):
            race_id = self._race_id(owner_id)
            if race_id:
                rules = self._rules(owner_id)
                effects = []
                if rules["first_volley_multiplier"] > 1:
                    effects.append(t('pierwsza salwa +{0}%').format(round((rules['first_volley_multiplier'] - 1) * 100)))
                if regeneration:
                    effects.append(t('regeneracja {0}% ran po rundzie').format(round(regeneration * 100)))
                if rules["damage_reduction"]:
                    effects.append(t('redukcja obrażeń {0}%').format(round(rules['damage_reduction'] * 100)))
                summary += t(' {0} — {1}: {2}; {3}.').format(label, t(RACES[race_id]['name']), t(RACES[race_id]['weapon_name']), join_text(", ", effects))
        self._report(attacker, t('Raport bitwy'), summary, "swarm/weapon" if defender == "khar" else "", f["swarm_crystals"])
        self._report(defender, t('Twoja kolonia została zaatakowana'), summary, "swarm/weapon" if attacker == "khar" else "")
        self._return(f)

    def state(self, player_id, planet_id=None):
        with self.lock:
            player = self._player(player_id)
            p = self._owned(player_id, planet_id)
            galaxy = []
            own = []
            for system in self.data["systems"]:
                view = {k: system[k] for k in ("id", "name", "x", "y", "galaxy_id")}
                view["galaxy_name"] = GALAXIES_BY_ID[system["galaxy_id"]]["name"]
                view["planets"] = []
                for pid in system["planet_ids"]:
                    q = self.data["planets"][pid]
                    item = {k: q[k] for k in ("id", "name", "system_id", "slot", "owner_type", "owner_id", "galaxy_id")}
                    item["owner_name"] = "" if q["owner_type"] == "empty" else t(self.data["alien"]["name"]) if q["owner_type"] == "alien" else self._player(q["owner_id"])["name"]
                    if q["owner_type"] == "player":
                        item["protected_until"] = self._player(q["owner_id"])["protected_until"]
                    race_id = self._race_id(q["owner_id"])
                    item.update(race_id=race_id, race_name=t(RACES[race_id]["name"]) if race_id else "",
                                colony_art=art_key(race_id, "colony"))
                    if q["owner_id"] == "khar":
                        item.update(swarm.public_planet(q, self.now))
                    view["planets"].append(item)
                    if q["owner_id"] == player_id:
                        own.append({k: item[k] for k in ("id", "name", "system_id", "race_id", "race_name", "colony_art", "galaxy_id")})
                galaxy.append(view)
            fleets = []
            alien_fleets = []
            incoming_attacks = []
            for f in self.data["fleets"].values():
                target = self.data["planets"][f["target_id"]]
                if (f["owner_id"] != player_id and f["status"] == "outbound"
                        and f["mission"] == "attack" and target["owner_id"] == player_id):
                    incoming_attacks.append({
                        "id": f["id"], "attacker_name": t(self.data["alien"]["name"]) if f["owner_id"] == "khar" else self._player(f["owner_id"])["name"],
                        "origin_name": self.data["planets"][f["origin_id"]]["name"], "target_name": target["name"],
                        "origin_id": f["origin_id"], "target_id": f["target_id"],
                        "arrives_at": f["arrives_at"], "seconds": f.get("seconds", 0),
                        "started_at": f.get("started_at", f["arrives_at"] - f.get("seconds", 0)),
                    })
                if f["owner_id"] != player_id and f["owner_id"] != "khar":
                    continue
                view = {k: copy.deepcopy(f[k]) for k in ("id", "origin_id", "target_id", "mission", "status", "ships", "arrives_at")}
                view["origin_name"] = self.data["planets"][f["origin_id"]]["name"]
                view["target_name"] = self.data["planets"][f["target_id"]]["name"]
                view["route"] = self._route_details(self.data["planets"][f["origin_id"]], target)
                race_id = self._race_id(f["owner_id"])
                view.update(race_id=race_id, race_name=t(RACES[race_id]["name"]) if race_id else "",
                            seconds=f.get("seconds", 0), cargo=copy.deepcopy(f.get("cargo", {})),
                            swarm_crystals=int(f.get("swarm_crystals", 0)))
                if f["owner_id"] == "khar":
                    role = "colonizer" if f["mission"] == "colonize" else "frigate"
                    view.update(race_id="swarm", race_name=t('Rój Khar'), art_key="swarm/" + role)
                    for private_key in ("ships", "cargo", "swarm_crystals"):
                        view.pop(private_key, None)
                (fleets if f["owner_id"] == player_id else alien_fleets).append(view)
            result = {"version": VERSION, "server_time": self.now, "speed": self.speed, "player": {k: player[k] for k in ("id", "name", "protected_until")}, "home_id": player["home_id"], "planet_id": p["id"], "planet_name": p["name"], "resources": {k: int(v) for k, v in p["resources"].items()}, "production": self.production(p), "energy": self.energy(p), "buildings": dict(p["buildings"]), "research": dict(player["research"]), "ships": dict(p["ships"]), "queue": copy.deepcopy(p["queue"]), "catalog": self._catalog(player_id, p), "own_planets": own, "galaxy": galaxy, "fleets": fleets, "reports": [public_report(report) for report in player["reports"]], "alien": {**self.data["alien"], "colonies_count": sum(q["owner_id"] == "khar" for q in self.data["planets"].values()), "fleets": alien_fleets}, "limits": {"colonies": MAX_COLONIES}}
            race_id = self._race_id(player_id)
            result["galaxies"] = self._public_galaxies(p, player_id)
            result["planet_galaxy_id"] = self._galaxy_id(p)
            result["limits"]["resource_cap"] = MAX_RESOURCE
            result["incoming_attacks"] = sorted(incoming_attacks, key=lambda item: (item["arrives_at"], item["id"]))
            protected = self._building_effects(p).get("protected_resources", 0)
            result["protected_resources"] = {key: int(min(protected, p["resources"][key])) for key in RESOURCES}
            result["account"] = self.account_status(player_id)
            empty_start = any(q["owner_type"] == "empty" and self._galaxy_id(q) == "g1" for q in self.data["planets"].values())
            result["sector"] = {"max_players": self.max_players, "players": len(self.data["players"]),
                                "registration_open": empty_start and (not self.max_players or len(self.data["players"]) < self.max_players)}
            result["player"].update(race_id=race_id, race_name=t(RACES[race_id]["name"]) if race_id else "",
                                    swarm_crystals=int(player.get("swarm_crystals", 0)))
            result["skill_tree"] = skill_tree.public_state(race_id, player.get("skill_nodes", []), player.get("swarm_crystals", 0))
            weak = [q for q in self.data["planets"].values() if q["owner_id"] == "khar"]
            recommended = min(weak, key=lambda q: (self._galaxy_id(q) != self._galaxy_id(p), int(q.get("swarm_crystals", 0)) < 1,
                                                   self._power(q["ships"], self._swarm_weapon_level(q), swarm.SHIPS),
                                                   self._distance(p, q), q["id"])) if weak else None
            result["alien"].update(name=t(self.data["alien"]["name"]), portrait_art="swarm/portrait", colony_art="swarm/colony", weapon_art="swarm/weapon",
                                   crystal_art="swarm/crystal", description=t(swarm.DESCRIPTION),
                                   max_colonies=swarm.MAX_COLONIES,
                                   recommended_target_id=recommended["id"] if recommended else "")
            result["races"] = [public_race(key) for key in RACES]
            result["race"] = public_race(race_id) if race_id else {}
            result["race_choice_reason"] = self._race_choice_reason(player_id)
            result["race_choice_allowed"] = not result["race_choice_reason"]
            result["colony_art"] = art_key(race_id, "colony")
            result["onboarding"] = onboarding.public_state(self.data, player, recommended_target_id=recommended["id"] if recommended else "", planet_id=p["id"])
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
                raise GameError(t('Zbyt wiele prób. Spróbuj ponownie za minutę.'), 429)
            attempts.append(now)


class Handler(BaseHTTPRequestHandler):
    server_version = "Pogranicze/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Do not log Authorization, credentials, bodies or full query strings.
        pass

    def _html(self, status, document):
        raw = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "public, max-age=900")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Accept-Language")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise GameError(t('Niedozwolony sposób przesyłania danych.'), 400)
        raw_length = self.headers.get("Content-Length", "0")
        if not re.fullmatch(r"[0-9]{1,8}", raw_length):
            raise GameError(t('Nieprawidłowy rozmiar żądania.'))
        length = int(raw_length)
        if length > MAX_BODY:
            raise GameError(t('Żądanie jest zbyt duże.'), 413)
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            raise GameError(t('Wymagane dane JSON.'), 415)
        try:
            def reject_constant(value):
                raise ValueError(value)
            data = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            # JSON's numeric exponent syntax can overflow a float without using
            # the non-standard NaN/Infinity tokens handled above.
            json.dumps(data, allow_nan=False)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise GameError(t('Nieprawidłowe dane JSON.'))
        if not isinstance(data, dict):
            raise GameError(t('Żądanie musi być obiektem JSON.'))
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
            if not world.write_healthy:
                raise GameError(t('Zapis gry jest chwilowo niedostępny.'), 503)
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
            raise GameError(t('Niedozwolona metoda.'), 405)
        auth_path = self.command == "POST" and path.path in ("/api/login", "/api/register", "/api/recover")
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
            if self.command == "POST" and path.path.startswith("/api/account/"):
                self.server.rate_limit(("sensitive-account", player_id), auth=True)
        body = self._body() if self.command == "POST" else None
        with world.lock:
            world.advance()
            if self.command == "POST" and path.path == "/api/register":
                return world.register(body.get("name"), body.get("password"), body.get("invite", ""))
            if self.command == "POST" and path.path == "/api/login":
                return world.login(body.get("name"), body.get("password"))
            if self.command == "POST" and path.path == "/api/recover":
                return world.recover_account(body.get("name"), body.get("recovery_code"), body.get("new_password"))
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
                return {"ok": True, "state": state, "message": t('Wylogowano.')}
            if self.command == "POST" and path.path == "/api/account/recovery-code":
                return world.account_recovery_code(token, body.get("password"))
            if self.command == "POST" and path.path == "/api/account/password":
                return world.account_password(token, body.get("password"), body.get("new_password"))
            if self.command == "POST" and path.path == "/api/account/logout-others":
                return world.account_logout_others(token, body.get("password"))
            if self.command == "POST" and path.path == "/api/account/delete":
                return world.account_delete(token, body.get("password"), body.get("confirmation"))
            raise GameError(t('Nie znaleziono adresu API.'), 404)

    def _serve(self):
        with language_scope(self.headers.get("Accept-Language", "en")):
            self._serve_localized()

    def _serve_localized(self):
        public_path = urlsplit(self.path).path
        if self.command == "GET" and public_path in ("/privacy", "/privacy/"):
            self._html(200, PRIVACY_HTML)
            return
        if self.command == "GET" and public_path in ("/delete-account", "/delete-account/"):
            self._html(200, ACCOUNT_DELETION_HTML)
            return
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
            print(t('Błąd obsługi żądania: {0}').format(type(exc).__name__), flush=True)
            self._json(500, {"ok": False, "error": t('Błąd serwera. Spróbuj ponownie.')})

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
    parser.add_argument("--speed", type=float, default=1)
    parser.add_argument("--max-players", type=int, default=0,
                        help=t('Opcjonalny limit kont; 0 (domyślnie) wyłącza limit. Nadal potrzebne są wolne planety.'))
    args = parser.parse_args(argv)
    if args.max_players < 0:
        parser.error(t('--max-players musi być nieujemną liczbą całkowitą'))
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
                print(t('Błąd aktualizacji świata: {0}').format(type(exc).__name__), flush=True)

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
