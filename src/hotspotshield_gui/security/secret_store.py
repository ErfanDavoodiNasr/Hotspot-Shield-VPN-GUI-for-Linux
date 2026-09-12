"""Credential storage using the desktop keyring with explicit opt-in fallbacks."""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hotspotshield_gui.utils.errors import PlaintextFallbackDisabledError

logger = logging.getLogger("hotspotshield_gui.security.secret_store")

SERVICE_NAME = "hotspotshield-gui"
USERNAME_KEY = "username"
PASSWORD_KEY = "password"  # noqa: S105 — keyring attribute name, not a secret


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str

    def is_complete(self) -> bool:
        return bool(self.username.strip()) and bool(self.password)


class SecretStore:
    """Loads and stores credentials without writing them into the repository."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or default_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_path = self.config_dir / "credentials.json"
        self._prefs_path = self.config_dir / "preferences.json"
        self._session: Credentials | None = None

    def load(self) -> Credentials | None:
        env_user = os.environ.get("HOTSPOTSHIELD_USERNAME", "").strip()
        env_pass = os.environ.get("HOTSPOTSHIELD_PASSWORD", "")
        if env_user and env_pass:
            return Credentials(env_user, env_pass)

        # Secret files only when explicitly opted in (tests / operators).
        # Never auto-load cwd/.secrets in production — cwd may be attacker-controlled.
        if _env_flag("HOTSPOTSHIELD_USE_SECRETS_FILE"):
            for directory in self._secret_file_dirs():
                file_creds = self._load_secret_files(directory)
                if file_creds is not None:
                    return file_creds

        try:
            import keyring

            username = keyring.get_password(SERVICE_NAME, USERNAME_KEY)
            password = keyring.get_password(SERVICE_NAME, PASSWORD_KEY) if username else None
            if username and password:
                return Credentials(username, password)
        except Exception as exc:  # noqa: BLE001 — keyring backends vary widely
            logger.debug("Keyring unavailable: %s", exc)

        # Existing opt-in plaintext file (created only with explicit allow flag).
        fallback = self._load_fallback()
        if fallback is not None:
            return fallback

        if self._session is not None:
            return self._session
        return None

    def save(self, credentials: Credentials) -> None:
        if not credentials.is_complete():
            raise ValueError("Incomplete credentials")

        stored_in_keyring = False
        try:
            import keyring

            keyring.set_password(SERVICE_NAME, USERNAME_KEY, credentials.username)
            keyring.set_password(SERVICE_NAME, PASSWORD_KEY, credentials.password)
            stored_in_keyring = True
            if self._fallback_path.exists():
                self._fallback_path.unlink()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to store credentials in keyring: %s", exc)

        if stored_in_keyring:
            self._session = None
            return

        # Session-only by default — never silently write plaintext passwords.
        self._session = credentials
        if _env_flag("HOTSPOTSHIELD_ALLOW_PLAINTEXT_FALLBACK"):
            self._save_fallback(credentials)
            return
        raise PlaintextFallbackDisabledError()

    def clear(self) -> None:
        self._session = None
        try:
            import keyring

            for key in (USERNAME_KEY, PASSWORD_KEY):
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except keyring.errors.PasswordDeleteError:
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.debug("Keyring clear failed: %s", exc)
        if self._fallback_path.exists():
            self._fallback_path.unlink()

    def load_preferences(self) -> dict[str, object]:
        if not self._prefs_path.exists():
            return {}
        try:
            data = json.loads(self._prefs_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_preferences(self, prefs: dict[str, object]) -> None:
        safe = {k: v for k, v in prefs.items() if "password" not in k.lower()}
        payload = json.dumps(safe, indent=2) + "\n"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".prefs.",
            suffix=".tmp",
            dir=str(self.config_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._prefs_path)
            self._prefs_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def _secret_file_dirs(self) -> list[Path]:
        dirs = [
            self.config_dir / ".secrets",
            Path.home() / ".config" / "hotspotshield-gui" / ".secrets",
        ]
        # CWD secrets only under explicit test flag (still requires USE_SECRETS_FILE).
        if _env_flag("HOTSPOTSHIELD_ALLOW_CWD_SECRETS"):
            dirs.insert(0, Path.cwd() / ".secrets")
        return dirs

    def _load_secret_files(self, directory: Path) -> Credentials | None:
        user_path = directory / "hotspotshield_username"
        pass_path = directory / "hotspotshield_password"
        if not user_path.exists() or not pass_path.exists():
            return None
        try:
            username = user_path.read_text(encoding="utf-8").strip()
            password = pass_path.read_text(encoding="utf-8").rstrip("\n")
        except OSError:
            return None
        if username and password:
            return Credentials(username, password)
        return None

    def _load_fallback(self) -> Credentials | None:
        if not self._fallback_path.exists():
            return None
        try:
            mode = self._fallback_path.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
                logger.warning("Insecure permissions on credentials fallback file")
            data = json.loads(self._fallback_path.read_text(encoding="utf-8"))
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", ""))
            if username and password:
                return Credentials(username, password)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to read credentials fallback: %s", exc)
        return None

    def _save_fallback(self, credentials: Credentials) -> None:
        payload = {
            "username": credentials.username,
            "password": credentials.password,
            "warning": "Unencrypted file created only because HOTSPOTSHIELD_ALLOW_PLAINTEXT_FALLBACK=1.",
        }
        self._fallback_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self._fallback_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def default_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "hotspotshield-gui"


def migrate_legacy_vpnconfig(path: Path) -> Credentials | None:
    """Read obsolete vpnconfig.py if present; never write passwords back to source."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    username = _extract_assignment(text, "vpnusername")
    password = _extract_assignment(text, "vpnpassword")
    if username and password and "your@email.here" not in username:
        return Credentials(username, password)
    return None


def _extract_assignment(source: str, name: str) -> str | None:
    import ast
    import re

    match = re.search(rf"^{name}\s*=\s*(.+)$", source, re.MULTILINE)
    if not match:
        return None
    try:
        value = ast.literal_eval(match.group(1).strip())
    except (SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None
