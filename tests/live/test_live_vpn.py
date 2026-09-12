"""Live VPN tests — opt-in only. Requires real CLI + secrets + suitable host."""

from __future__ import annotations

import shutil

import pytest

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.security.secret_store import Credentials, SecretStore
from hotspotshield_gui.services.vpn_service import VpnService

pytestmark = pytest.mark.live


def _load_live_credentials() -> Credentials:
    store = SecretStore()
    creds = store.load()
    if creds and creds.is_complete():
        return creds
    pytest.skip("No live credentials available in .secrets/ or environment")


def _assert_cli_environment(client: HotspotShieldClient) -> None:
    """Skip when the vendor CLI cannot operate in this environment (e.g. Docker Desktop)."""
    start = client.start_service()
    combined = start.combined.lower()
    blockers = (
        "root user",
        "device uuid",
        "environment information",
        "bonding_masters",
        "can't start/connect",
    )
    if any(b in combined for b in blockers) and start.returncode != 0:
        pytest.skip(
            "Hotspot Shield CLI cannot start in this environment "
            f"(need a real Linux desktop/VM with device access): {start.combined[:200]}"
        )


@pytest.fixture(scope="module")
def live_service() -> VpnService:
    if shutil.which("hotspotshield") is None:
        pytest.skip("hotspotshield CLI not installed")
    client = HotspotShieldClient()
    _assert_cli_environment(client)
    return VpnService(client)


def test_live_authentication(live_service: VpnService) -> None:
    creds = _load_live_credentials()
    live_service.ensure_signed_in(creds)
    status = live_service.client.account_status()
    assert "signed in" in status.lower()
    assert "not signed" not in status.lower()


def test_live_locations(live_service: VpnService) -> None:
    creds = _load_live_credentials()
    live_service.ensure_signed_in(creds)
    locations = live_service.list_locations()
    assert locations
    assert all(loc.code for loc in locations)


def test_live_connect_disconnect_switch(live_service: VpnService) -> None:
    creds = _load_live_credentials()
    locations = live_service.list_locations()
    assert len(locations) >= 1
    primary = locations[0]
    secondary = locations[1] if len(locations) > 1 else locations[0]

    try:
        live_service.disconnect(settle_seconds=1)
    except Exception:
        pass

    info = live_service.connect(primary, creds, settle_seconds=2)
    assert info.state.value == "connected"
    if secondary.code != primary.code:
        info = live_service.switch_location(secondary, creds)
        assert info.state.value == "connected"
        assert info.connected_location_code == secondary.code
    info = live_service.disconnect(settle_seconds=2)
    assert info.state.value == "disconnected"

    info = live_service.connect(primary, creds, settle_seconds=2)
    assert info.state.value == "connected"
    live_service.disconnect(settle_seconds=2)
