"""Redaction and secret store tests."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from hotspotshield_gui.security.redaction import redact_mapping, redact_text
from hotspotshield_gui.security.secret_store import Credentials, SecretStore


def test_redact_password_assignment() -> None:
    assert "***" in redact_text("password=supersecret")
    assert "supersecret" not in redact_text("password=supersecret")


def test_redact_extra_secrets() -> None:
    text = redact_text("user used SuperSecretValue99 today", extra_secrets=["SuperSecretValue99"])
    assert "SuperSecretValue99" not in text
    assert "***" in text


def test_redact_mapping() -> None:
    out = redact_mapping({"username": "a@b.c", "password": "x", "ok": "yes"})
    assert out["password"] == "***"
    assert out["ok"] == "yes"


def test_secret_store_fallback_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HOTSPOTSHIELD_USERNAME", raising=False)
    monkeypatch.delenv("HOTSPOTSHIELD_PASSWORD", raising=False)
    store = SecretStore(config_dir=tmp_path)
    # Force fallback by making keyring fail via missing optional path — save uses keyring first.
    # We call _save_fallback directly for permission assertion.
    store._save_fallback(Credentials("a@b.c", "secret"))
    mode = store._fallback_path.stat().st_mode
    assert mode & (stat.S_IRGRP | stat.S_IROTH) == 0
    loaded = store._load_fallback()
    assert loaded is not None
    assert loaded.username == "a@b.c"


def test_secret_files_loader(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HOTSPOTSHIELD_USERNAME", raising=False)
    monkeypatch.delenv("HOTSPOTSHIELD_PASSWORD", raising=False)
    monkeypatch.setenv("HOTSPOTSHIELD_USE_SECRETS_FILE", "1")
    secrets = tmp_path / ".secrets"
    secrets.mkdir()
    (secrets / "hotspotshield_username").write_text("u@e.com", encoding="utf-8")
    (secrets / "hotspotshield_password").write_text("pw", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    store = SecretStore(config_dir=tmp_path / "cfg")
    creds = store.load()
    assert creds is not None
    assert creds.username == "u@e.com"
    assert creds.password == "pw"


def test_preferences_never_store_password(tmp_path: Path) -> None:
    store = SecretStore(config_dir=tmp_path)
    store.save_preferences({"theme": "dark", "password": "nope"})
    data = json.loads((tmp_path / "preferences.json").read_text(encoding="utf-8"))
    assert "password" not in data
