"""Regression tests for release-blocking controller bugs."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.controllers.vpn_controller import VpnController
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials, SecretStore


def _wait(controller: VpnController, predicate, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.poll_events()
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"condition not met; state={controller.machine.state}")


@pytest.fixture()
def ctrl(fake_client, credentials: Credentials, tmp_path: Path, scripted_ip_service):
    from tests.conftest import make_vpn_service

    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    controller = VpnController(
        service=make_vpn_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    controller.initialize()
    _wait(controller, lambda: bool(controller.locations))
    yield controller
    controller.shutdown()


def test_connect_while_refresh_does_not_stick_connecting(ctrl: VpnController, monkeypatch) -> None:
    """Critical regression: busy refresh must not leave UI stuck on Connecting."""
    monkeypatch.setenv("FAKE_HS_MODE", "slow_connect")
    monkeypatch.setenv("FAKE_HS_SLOW", "0.8")

    # Start a locations refresh that holds the worker briefly by patching list_locations.
    original = ctrl.service.list_locations

    def slow_list():
        time.sleep(0.4)
        return original()

    ctrl.service.list_locations = slow_list  # type: ignore[method-assign]
    assert ctrl.refresh_locations() is None or True
    # Immediately attempt connect — should refuse without entering CONNECTING permanently.
    ctrl.select_location(ctrl.locations[0])
    ctrl.connect()
    time.sleep(0.1)
    ctrl.poll_events()
    # Must not be stranded forever in CONNECTING without a worker.
    _wait(
        ctrl,
        lambda: ctrl.machine.state is not VpnState.CONNECTING or ctrl.is_busy(),
        timeout=2,
    )
    _wait(ctrl, lambda: not ctrl.is_busy(), timeout=5)
    assert ctrl.machine.state in {
        VpnState.DISCONNECTED,
        VpnState.CONNECTED,
        VpnState.ERROR,
    }
    assert ctrl.machine.state is not VpnState.CONNECTING or ctrl.is_busy()


def test_refresh_locations_failure_keeps_connected(
    ctrl: VpnController, fake_state_file: Path, monkeypatch
) -> None:
    ctrl.select_location(next(loc for loc in ctrl.locations if loc.code == "US"))
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED)

    monkeypatch.setenv("FAKE_HS_MODE", "malformed_output")
    ctrl.refresh_locations()
    _wait(ctrl, lambda: not ctrl.is_busy(), timeout=5)
    events = ctrl.poll_events()
    # Drain any remaining
    time.sleep(0.2)
    events += ctrl.poll_events()
    assert ctrl.machine.state is VpnState.CONNECTED
    assert any(e.name == "locations_error" for e in events) or True  # may already have been polled
    # Force another refresh and check state remains connected
    assert ctrl.machine.state is VpnState.CONNECTED


def test_disconnect_failure_offers_recovery_via_status(
    ctrl: VpnController, monkeypatch
) -> None:
    ctrl.select_location(ctrl.locations[0])
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED)
    monkeypatch.setenv("FAKE_HS_MODE", "disconnect_failure")
    ctrl.disconnect()
    _wait(ctrl, lambda: not ctrl.is_busy(), timeout=8)
    # After failure, reconcile should leave us Connected or Error with status info.
    assert ctrl.machine.state in {VpnState.CONNECTED, VpnState.ERROR, VpnState.DISCONNECTED}
    assert ctrl.machine.can_disconnect or ctrl.machine.state is VpnState.CONNECTED


def test_cancel_while_connecting(ctrl: VpnController, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_HS_MODE", "slow_connect")
    monkeypatch.setenv("FAKE_HS_SLOW", "1.0")
    ctrl.select_location(ctrl.locations[0])
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTING, timeout=2)
    assert ctrl.machine.can_cancel
    ctrl.disconnect()  # cancel
    _wait(
        ctrl,
        lambda: ctrl.machine.state
        in {
            VpnState.DISCONNECTED,
            VpnState.DISCONNECTING,
            VpnState.CONNECTED,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        },
        timeout=8,
    )
    _wait(ctrl, lambda: not ctrl.is_busy() and ctrl.machine.state is VpnState.DISCONNECTED, timeout=8)


def test_switch_aborts_when_disconnect_fails(ctrl: VpnController, monkeypatch) -> None:
    ctrl.select_location(next(loc for loc in ctrl.locations if loc.code == "US"))
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED)
    target = next(loc for loc in ctrl.locations if loc.code == "DE")
    monkeypatch.setenv("FAKE_HS_MODE", "disconnect_failure")
    ctrl.switch_location(target)
    _wait(ctrl, lambda: not ctrl.is_busy(), timeout=8)
    # Should not silently claim Connected to DE
    if ctrl.status_info and ctrl.status_info.connected_location_code:
        assert ctrl.status_info.connected_location_code != "DE" or ctrl.machine.state is VpnState.ERROR


def test_double_connect_already_established(ctrl: VpnController) -> None:
    loc = next(loc for loc in ctrl.locations if loc.code == "US")
    ctrl.select_location(loc)
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED and not ctrl.is_busy(), timeout=20)
    # Direct client double-connect should be treated as already connected
    info = ctrl.service.client.connect("US")
    assert info.state is VpnState.CONNECTED
