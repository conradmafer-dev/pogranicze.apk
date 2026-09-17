# Alien Colonies 0.6.0 — serwer Railway

Kompletny, płaski katalog wdrożeniowy dla istniejącego serwera multiplayer.
Jest częścią jednego pełnego ZIP-a projektu. Nowy moduł **galaxies.py jest obowiązkowy**.

## Wdrożenie bez resetu

1. Przed wdrożeniem zachowaj spójną kopię bazy poza Railway. Możesz użyć
   ukończonej kopii z `/data/backups/`. Kopie na samym Volume nie chronią
   przed utratą całego Volume.
2. W swoim istniejącym repozytorium GitHub podmień pliki na CAŁĄ zawartość
   tego folderu: `app.py`, `galaxies.py`, `races.py`, `skill_tree.py`, `swarm.py`,
   `swarm_ai.py`, `accounts.py`, `onboarding.py`, `backups.py`, `i18n.py`,
   `run.py`, `Dockerfile`, `railway.toml` i pięć plików językowych
   `en.json`, `pl.json`, `de.json`, `es.json`, `fr.json`.
   Pliki mają leżeć obok siebie w katalogu głównym repozytorium. Nie dodawaj
   folderu całego projektu ani samego archiwum ZIP jako pliku do wdrożenia.
3. Zachowaj istniejącą usługę, domenę i **Volume zamontowany jako `/data`**.
   Baza pozostaje pod `/data/private_test.sqlite3`. Nie kasuj jej, nie twórz
   nowego Volume, nie zwiększaj liczby replik ponad jedną.
4. Commit uruchomi wdrożenie zgodnie z Twoją istniejącą konfiguracją GitHub/Railway.
   Dockerfile nie wymaga folderu `localization/`: wszystkie języki są obok app.py.
5. Po uruchomieniu sprawdź `/health`: pole `version` ma wynosić **0.6.0**.
   Sprawdź też `/privacy` i `/delete-account`. Migracja dopisuje pięć galaktyk
   i zapisuje kopię przed zmianą istniejącego świata. Błąd kopii zatrzymuje
   migrację zamiast narażać jedyny zapis.

Nowe galaktyki dostępne są w kliencie 0.6.0 / kod 27. Sam serwer nie aktualizuje
aplikacji na telefonie. Wersja sklepu aktualizuje się przez Google Play.

## Zmienne

Zachowaj swój limit kont `PGR_MAX_PLAYERS` i tempo `PGR_SPEED` (standardowo 1).
Nowa przestrzeń nie znosi istniejącego limitu kont. Domyślny limit hostingu to
15 kont, nie 15 równocześnie zalogowanych osób. Konta już istniejące zachowują dostęp.

Po udostępnieniu nowego klienta w Google Play:

```text
PGR_LATEST_VERSION_CODE=27
PGR_LATEST_VERSION=0.6.0
PGR_MIN_VERSION_CODE=0
```

Jeśli wyeksportujesz AAB z innym wyższym kodem, użyj tego kodu.
Nie ustawiaj minimum na 27 przed udostępnieniem i sprawdzeniem nowego klienta.
Nie dodawaj zmiennych starego pobierania APK: `PGR_DOWNLOAD_URL`, `PGR_APK_SHA256`,
`PGR_APK_SIZE_BYTES`, `PGR_UPDATE_MESSAGE`. Pozostałości starej konfiguracji
nie są potrzebne klientowi sklepowemu. Nie wpisuj ręcznie `PORT`,
`RAILWAY_VOLUME_MOUNT_PATH` ani `RAILWAY_SERVICE_ID`.

## Co zachowuje migracja

Stare s1–s30 i ich planety zostają w Aurorze. Konta, sesje, hasła, kod odzyskiwania,
floty, kolejki, umiejętności i zwykłe zasoby nie są resetowane. Nowe planety
mają nowe identyfikatory. Każda nowa galaktyka dostaje jeden silny ul tylko
przy pierwszym dodaniu; restart nie odtwarza zniszczonych gniazd ani ich zapasów.

Łącznie: sześć galaktyk / 180 układów / 540 planet. Limit kolonii gracza: 12;
limit zapasu pojedynczego zwykłego surowca na planecie: 1 miliard. Rój ma
8 początkowych twierdz i globalny limit 13 kolonii. Zachowano limit jednej
kolonizacji na siedem rzeczywistych dni, powolne odnawianie rzadkich kryształów
oraz ochronę nowych graczy. Cele wypraw AI są lokalne dla ich galaktyki.

Paliwo dla lotów między galaktykami jest liczone i pobierane po stronie serwera.
Klient nie może obniżyć ceny przez zmianę żądania. Podgląd z flagą
`allow_unaffordable` pokazuje brakujące zapasy, ale nie pozwala wysłać floty.
Droga powrotna nie wymaga drugiego pobrania paliwa.

## Test lokalny (bez kont produkcyjnych)

Python 3.11+; brak dodatkowych zależności serwera:

```text
python run.py --local-data test-data --port 8080
```

Ten tryb słucha tylko na 127.0.0.1. Nie uruchamiaj go na kopii bazy produkcyjnej
bez świadomej izolacji środowiska. Na Railway używane jest `python run.py`,
bez `--local-data`, z istniejącym Volume.

## Polityka i konta

`/privacy` i `/delete-account` pozostają publiczne. Kontakt:
`conradmafer@gmail.com`. Zwykła rejestracja nadal używa nazwy i hasła.
Google Sign-In i AdMob NIE zostały dodane w tym wydaniu.

W tej paczce nie ma zapisów graczy, haseł, tokenów ani klucza podpisu Android.
Zdalnego wdrożenia nie przeprowadzono automatycznie z rozmowy.
