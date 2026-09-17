"""Bounded local SQLite backups; a failed copy never touches the live database."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import time
import uuid


class SQLiteBackups:
    def __init__(self, database_path, interval=3600, retention=24):
        self.directory = None if str(database_path) == ":memory:" else Path(database_path).resolve().parent / "backups"
        self.interval = max(60, int(interval))
        self.retention = max(2, min(168, int(retention)))
        self.next_at = 0.0
        self.healthy = True
        self.last_backup = ""

    def maybe_create(self, connection, *, force=False, clock=None):
        """Call only with the world lock held, after a committed transaction."""
        now = time.monotonic() if clock is None else float(clock)
        if self.directory is None or (not force and now < self.next_at):
            return None
        # Retry errors at most once per minute, successful copies once per hour.
        self.next_at = now + 60
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            name = f"galaxy-{stamp}-{uuid.uuid4().hex[:8]}.sqlite3"
            destination = self.directory / name
            temporary = self.directory / (name + ".part")
            backup = sqlite3.connect(str(temporary))
            try:
                connection.backup(backup, pages=256)
                # The copied database can inherit WAL mode. Consolidate it into
                # one portable file before renaming, while its original path and
                # sidecars still agree. A Connection context manager commits but
                # does not close its handle; explicit close is required here.
                backup.commit()
                if backup.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
                    raise sqlite3.DatabaseError("Backup checkpoint failed")
                if backup.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                    raise sqlite3.DatabaseError("Backup journal conversion failed")
                if backup.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise sqlite3.DatabaseError("Backup verification failed")
            finally:
                backup.close()
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            files = sorted(self.directory.glob("galaxy-*.sqlite3"), key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
            for expired in files[self.retention:]:
                expired.unlink()
            self.last_backup = name
            self.next_at = now + self.interval
            self.healthy = True
            return destination
        except (OSError, sqlite3.Error) as exc:
            self.healthy = False
            print(f"Kopia zapasowa odroczona: {type(exc).__name__}", flush=True)
            return None
        finally:
            if temporary is not None:
                # Only this attempt's temporary files are eligible for cleanup;
                # the live database and successfully retained copies stay intact.
                for suffix in ("", "-wal", "-shm", "-journal"):
                    try:
                        Path(str(temporary) + suffix).unlink(missing_ok=True)
                    except OSError:
                        pass
