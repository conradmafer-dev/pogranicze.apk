"""Account lifecycle helpers for World, with no credentials in world snapshots.

World supplies its lock, _atomic transaction, GameError class and existing password
and session helpers. Every check and mutation occurs inside the same transaction.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t

import hashlib
import hmac
import secrets


class AccountManagementMixin:
    def _init_account_management(self):
        # A separate table preserves the original four-column accounts schema.
        self.db.execute("""CREATE TABLE IF NOT EXISTS account_recovery (
            player_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
            code_hash TEXT NOT NULL
        )""")

    @staticmethod
    def _recovery_digest(code):
        if not isinstance(code, str) or len(code) > 128:
            return None
        normalized = code.strip().upper().replace("-", "").replace(" ", "")
        if (not normalized.startswith("AC") or len(normalized) != 50
                or any(c not in "0123456789ABCDEF" for c in normalized[2:])):
            return None
        return hashlib.sha256(("alien-colonies-recovery-v1:" + normalized).encode("ascii")).hexdigest()

    def account_status(self, player_id):
        with self.lock:
            self._player(player_id)
            exists = self.db.execute(
                "SELECT 1 FROM account_recovery WHERE player_id=?", (player_id,)).fetchone()
            return {"recovery_code_enabled": bool(exists)}

    def _reauth_account(self, token, password):
        player_id = self.authenticate(token)
        row = self.db.execute(
            "SELECT salt,password_hash FROM accounts WHERE id=?", (player_id,)).fetchone()
        if (not row or not isinstance(password, str) or not 8 <= len(password) <= 128
                or not hmac.compare_digest(self._password_hash(password, row[0]), row[1])):
            raise self.account_error_class(t('Nieprawidłowe obecne hasło.'), 403)
        self._player(player_id)
        return player_id

    def account_recovery_code(self, token, password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            secret = secrets.token_hex(24).upper()
            code = "AC-" + "-".join(secret[i:i + 8] for i in range(0, len(secret), 8))
            self.db.execute("""INSERT INTO account_recovery(player_id,code_hash) VALUES(?,?)
                ON CONFLICT(player_id) DO UPDATE SET code_hash=excluded.code_hash""",
                (player_id, self._recovery_digest(code)))
            self._save(commit=False)
            return {"ok": True, "recovery_code": code,
                    "message": t('Zapisz kod w bezpiecznym miejscu. Poprzedni kod przestał działać; ten zobaczysz tylko teraz.')}

    def _replace_account_password(self, player_id, new_password):
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(new_password, salt)
        self.db.execute("UPDATE accounts SET salt=?,password_hash=? WHERE id=?",
                        (salt, password_hash, player_id))
        self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
        self.db.execute("DELETE FROM account_recovery WHERE player_id=?", (player_id,))
        return self._session(player_id)

    def recover_account(self, name, recovery_code, new_password):
        # Validating the new password before any mutation also protects existing
        # passwords, sessions and the single-use code from an invalid request.
        name, new_password = self._credentials(name, new_password)
        digest = self._recovery_digest(recovery_code)
        with self.lock, self._atomic():
            row = self.db.execute("""SELECT a.id,r.code_hash FROM accounts a
                JOIN account_recovery r ON r.player_id=a.id WHERE a.name_key=?""",
                (name.casefold(),)).fetchone()
            matches = hmac.compare_digest(digest or ("0" * 64), row[1] if row else ("f" * 64))
            if not digest or not row or not matches:
                raise self.account_error_class(t('Nieprawidłowa nazwa lub kod odzyskiwania.'), 401)
            player_id = row[0]
            self._player(player_id)
            token = self._replace_account_password(player_id, new_password)
            self._save(commit=False)
            return {"ok": True, "token": token, "state": self.state(player_id),
                    "message": t('Odzyskano konto. Pozostałe sesje i użyty kod wygasły. W ustawieniach utwórz nowy kod.')}

    def account_password(self, token, password, new_password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            _, new_password = self._credentials(self._player(player_id)["name"], new_password)
            new_token = self._replace_account_password(player_id, new_password)
            self._save(commit=False)
            return {"ok": True, "token": new_token, "state": self.state(player_id),
                    "message": t('Hasło zmienione. Pozostałe sesje i kod odzyskiwania wygasły. Utwórz nowy kod.')}

    def account_logout_others(self, token, password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            self.db.execute("DELETE FROM sessions WHERE player_id=? AND token_hash<>?",
                            (player_id, token_hash))
            self._save(commit=False)
            return {"ok": True, "message": t('Wylogowano pozostałe urządzenia.')}

    def account_delete(self, token, password, confirmation):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            if confirmation not in ("DELETE ACCOUNT", "USUŃ KONTO"):
                raise self.account_error_class(t('Wpisz dokładnie {0}, aby potwierdzić usunięcie.').format('DELETE ACCOUNT'), 400)
            for planet_id, planet in list(self.data["planets"].items()):
                if planet["owner_id"] == player_id:
                    # Keep the galaxy's physical location, discard all private
                    # colony content, including newer racial/Swarm-specific keys.
                    self.data["planets"][planet_id] = self._planet(
                        planet_id, planet["name"], planet["system_id"], planet["slot"])
            for fleet_id, fleet in list(self.data["fleets"].items()):
                if fleet["owner_id"] == player_id:
                    del self.data["fleets"][fleet_id]
            # Other fleets remain the same real flights, with the same cargo and
            # deadlines. Existing settlement rules cancel attacks on empty targets
            # and allow scouts/colonizers to observe the newly free planet.
            self.data["players"].pop(player_id)
            self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
            self.db.execute("DELETE FROM account_recovery WHERE player_id=?", (player_id,))
            self.db.execute("DELETE FROM accounts WHERE id=?", (player_id,))
            self._save(commit=False)
            return {"ok": True, "deleted": True,
                    "message": t('Konto i jego imperium zostały usunięte z aktywnego świata.')}
