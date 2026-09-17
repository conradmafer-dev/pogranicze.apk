"""Railway entry point: durable world, injected port, one writer, trusted edge."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import app


class WorldFileLock:
    def __init__(self, directory: Path):
        self.stream = (directory / "world.lock").open("a+b")
        try:
            if self.stream.seek(0, 2) == 0:
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise RuntimeError("Ta galaktyka jest juz uruchomiona. Ustaw jedna replike serwera.") from exc

    def close(self):
        self.stream.close()


def configuration(local_data: Path | None, port: int | None, env: dict) -> tuple[Path, list[str], str | None]:
    if local_data is None:
        mount = env.get("RAILWAY_VOLUME_MOUNT_PATH")
        if not env.get("RAILWAY_SERVICE_ID") or not mount:
            raise ValueError("Dodaj w Railway trwaly Volume do tej uslugi z Mount Path /data. Zmienne RAILWAY_VOLUME_MOUNT_PATH nie wpisuj recznie. Potem wybierz Redeploy.")
        directory = Path(mount)
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError("Dysk Railway nie jest zamontowany. Sprawdz Volume i Mount Path /data.")
        host = "0.0.0.0"
        trusted_header = "X-Real-IP"
    else:
        if env.get("RAILWAY_SERVICE_ID"):
            raise ValueError("Na Railway uzyj podlaczonego Volume, bez --local-data.")
        directory = local_data.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        host = "127.0.0.1"
        trusted_header = None
    server_port = port if port is not None else int(env.get("PORT", "8080"))
    if not 1 <= server_port <= 65535:
        raise ValueError("PORT musi miec wartosc od 1 do 65535.")
    argv = ["--host", host, "--port", str(server_port),
            "--db", str(directory / "private_test.sqlite3"),
            "--speed", env.get("PGR_SPEED", "1"),
            "--max-players", env.get("PGR_MAX_PLAYERS", "15" if local_data is None else "0")]
    return directory, argv, trusted_header


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-data", type=Path, help="Explicit local PC smoke test; no hosted volume")
    parser.add_argument("--port", type=int, help="Local test port; Railway normally injects PORT")
    args = parser.parse_args()
    world_lock = None
    try:
        directory, argv, trusted_header = configuration(args.local_data, args.port, dict(os.environ))
        world_lock = WorldFileLock(directory)
        print("Alien Colonies: trwaly zapis gotowy; uruchamiam wspolny wszechswiat (6 galaktyk).", flush=True)
        app.main(argv=argv, trust_proxy_header=trusted_header)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Nie uruchomiono serwera: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if world_lock is not None:
            world_lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
