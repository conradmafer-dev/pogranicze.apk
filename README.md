# Alien Colonies — serwer Railway 0.2.0

Autorytatywny serwer trzech ras, koła 60 umiejętności i ekspansji Roju. Kryształy Roju powstają tylko u NPC, są zdobywane podczas zwycięskich wypraw, dostarczane po powrocie floty i wydawane na sąsiadujące umiejętności. Zwykłe surowce pozostają osobnym systemem.

## Wgranie

Do głównego katalogu repozytorium `pogranicze-serwer` wgraj wszystkie **8 plików**: `app.py`, `races.py`, **`skill_tree.py`**, **`swarm.py`**, `run.py`, `Dockerfile`, `railway.toml`, `README.md`. Nowe moduły są wymagane; zaktualizowany Dockerfile kopiuje je do obrazu.

Zatwierdź commit i poczekaj na wdrożenie istniejącej usługi Railway. Zachowaj domenę, Volume `/data`, jedną replikę i wyłączone usypianie. `PORT` i `RAILWAY_VOLUME_MOUNT_PATH` pochodzą z hostingu; nie wpisuj ręcznie zmiennej udającej dysk.

Po wdrożeniu `/health` ma zwrócić `{"ok":true,"version":"0.2.0"}`. Klient 0.2.0 pokazuje koło, nową walutę i grafiki Roju. Baza znajduje się nadal w `/data/private_test.sqlite3`. Pierwsze uruchomienie tej wersji jednorazowo odbudowuje front NPC: trzy silne ule i cztery słabe przyczółki. Stare floty Roju są wycofane; imperia graczy pozostają. Kolejne restarty nie powtarzają tej operacji i nie przyznają graczom kryształów.

## APK i zmienne aktualizatora

Po opublikowaniu i sprawdzeniu rzeczywistego APK 0.2.0 ustaw:

```text
PGR_LATEST_VERSION_CODE=14
PGR_LATEST_VERSION=0.2.0
PGR_MIN_VERSION_CODE=0
```

W `PGR_DOWNLOAD_URL` wklej bezpośredni link do nowego APK z GitHub Assets. `PGR_APK_SHA256` i `PGR_APK_SIZE_BYTES` muszą odpowiadać temu plikowi; eksport tworzy je w `DANE_AKTUALIZACJI_RAILWAY.txt`. Wdróż zmienne i sprawdź `/api/client-version`: kod 14, nazwa 0.2.0, właściwy link, hash oraz rozmiar.

Po udanej instalacji aktualizacji można ustawić `PGR_MIN_VERSION_CODE=14`, aby wymagać nowego klienta. Health i manifest APK mają oddzielne wersje. Domyślny manifest nie ogłasza nowego pobrania: nadal ma kod6/nazwę0.1.5/minimum0, pusty URL i hash oraz rozmiar0. Wdrożenie serwera samo nie publikuje APK.

## Sprawdzenie lokalne

Python 3.11+, bez dodatkowych bibliotek:

```text
python run.py --local-data test-data --port 8080
```

Ten tryb nasłuchuje wyłącznie na 127.0.0.1. Na Railway użyj `python run.py` z podłączonym Volume. Paczka nie zawiera zapisanej gry, haseł, tokenów ani klucza APK.
