"""Failure-injection coverage for fake CLI modes."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.cli.process_runner import ProcessRunner
from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.controllers.vpn_controller import VpnController
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials, SecretStore
from hotspotshield_gui.utils.errors import (
    AuthenticationError,
    CliTimeoutError,
)


def _client(fake_hotspotshield: Path) -> HotspotShieldClient:
    return HotspotShieldClient(ProcessRunner(), executable=str(fake_hotspotshield))


def test_network_failure_mode(fake_hotspotshield: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "network_failure")
    client = _client(fake_hotspotshield)
    result = client.start_service()
    assert result.returncode != 0


def test_empty_locations_mode(fake_hotspotshield: Path, fake_state_file: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "empty_locations")
    client = _client(fake_hotspotshield)
    locs = client.locations()
    assert locs == []


def test_malformed_locations_controller(
    fake_hotspotshield: Path,
    credentials: Credentials,
    tmp_path: Path,
    fake_state_file: Path,
    monkeypatch,
    scripted_ip_service,
) -> None:
    from tests.conftest import make_vpn_service

    monkeypatch.setenv("FAKE_HS_MODE", "malformed_output")
    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    ctrl = VpnController(
        service=make_vpn_service(_client(fake_hotspotshield), scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    deadline = time.time() + 5
    saw_error = False
    while time.time() < deadline:
        for e in ctrl.poll_events():
            if e.name == "locations_error":
                saw_error = True
                break
        if saw_error:
            break
        time.sleep(0.05)
    ctrl.shutdown()
    assert saw_error
    assert ctrl.machine.state is not VpnState.CONNECTING


def test_timeout_mode(fake_hotspotshield: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "timeout")
    monkeypatch.setenv("FAKE_HS_TIMEOUT_SLEEP", "2")
    client = HotspotShieldClient(ProcessRunner(default_timeout=0.3), executable=str(fake_hotspotshield))
    with pytest.raises(CliTimeoutError):
        client.status(timeout=0.3)


def test_permission_denied_mode(fake_hotspotshield: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "permission_denied")
    client = _client(fake_hotspotshield)
    result = client.runner.run([str(fake_hotspotshield), "status"], timeout=5)
    assert result.returncode == 126


def test_auth_failure_message_quality(fake_hotspotshield: Path, fake_state_file: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "auth_failure")
    fake_state_file.write_text(
        json.dumps({"vpn": "disconnected", "location": None, "signed_in": False, "username": None}),
        encoding="utf-8",
    )
    client = _client(fake_hotspotshield)
    with pytest.raises(AuthenticationError) as exc:
        client.sign_in(Credentials("bad@example.com", "wrong"))
    assert "Premium" in exc.value.user_message or "sign in" in exc.value.user_message.lower()
    assert "traceback" not in exc.value.user_message.lower()
