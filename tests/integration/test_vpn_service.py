"""CLI client + VPN service integration against fake executable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.services.vpn_service import VpnService
from hotspotshield_gui.utils.errors import (
    AuthenticationError,
    LocationUnavailableError,
)


def test_status_disconnected(fake_client) -> None:
    info = fake_client.status()
    assert info.state is VpnState.DISCONNECTED


def test_locations_requires_signin_or_state(fake_client, fake_state_file: Path) -> None:
    # Fixture starts signed_in=True
    locs = fake_client.locations()
    assert any(loc.code == "US" for loc in locs)


def test_connect_disconnect_cycle(fake_client) -> None:
    info = fake_client.connect("DE")
    assert info.state is VpnState.CONNECTED
    assert info.connected_location_code == "DE"
    info = fake_client.disconnect()
    assert info.state is VpnState.DISCONNECTED


def test_connect_rejects_injection_payload(fake_client) -> None:
    with pytest.raises(LocationUnavailableError):
        fake_client.connect("US; rm -rf /")


def test_connect_rejects_whitespace_code(fake_client) -> None:
    with pytest.raises(LocationUnavailableError):
        fake_client.connect("US NY")


def test_switch_via_service(fake_client, credentials: Credentials) -> None:
    service = VpnService(fake_client)
    service.connect("US", credentials, settle_seconds=0)
    info = service.switch_location("DE", credentials)
    assert info.state is VpnState.CONNECTED
    assert info.connected_location_code == "DE"


def test_auth_failure_mode(fake_hotspotshield: Path, fake_state_file: Path, monkeypatch) -> None:
    from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
    from hotspotshield_gui.cli.process_runner import ProcessRunner

    monkeypatch.setenv("FAKE_HS_MODE", "auth_failure")
    # Reset signed_in
    fake_state_file.write_text(
        json.dumps({"vpn": "disconnected", "location": None, "signed_in": False, "username": None}),
        encoding="utf-8",
    )
    client = HotspotShieldClient(ProcessRunner(), executable=str(fake_hotspotshield))
    with pytest.raises(AuthenticationError):
        client.sign_in(Credentials("bad@example.com", "wrong"))


def test_double_connect_already_established(fake_client) -> None:
    fake_client.connect("US")
    info = fake_client.connect("DE")
    assert info.state is VpnState.CONNECTED


def test_ordering_connect_disconnect_disconnect(fake_client) -> None:
    fake_client.connect("US")
    fake_client.disconnect()
    info = fake_client.disconnect()
    assert info.state is VpnState.DISCONNECTED
