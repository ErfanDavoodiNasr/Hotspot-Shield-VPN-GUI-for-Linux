"""Controller concurrency / ordering tests."""

from __future__ import annotations

import time

from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.controllers.vpn_controller import VpnController
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials, SecretStore


def _wait_until(controller: VpnController, predicate, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.poll_events()
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


def test_controller_connect_disconnect(
    fake_client, credentials: Credentials, tmp_path, scripted_ip_service
) -> None:
    from tests.conftest import make_vpn_service

    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    controller = VpnController(
        service=make_vpn_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    controller.initialize()
    _wait_until(controller, lambda: bool(controller.locations), timeout=8)
    assert controller.machine.state in {VpnState.DISCONNECTED, VpnState.CONNECTED, VpnState.ERROR}
    controller.select_location(next(loc for loc in controller.locations if loc.code == "US"))
    controller.connect()
    _wait_until(
        controller,
        lambda: controller.machine.state is VpnState.CONNECTED and not controller.is_busy(),
        timeout=15,
    )
    controller.disconnect()
    _wait_until(
        controller,
        lambda: controller.machine.state is VpnState.DISCONNECTED and not controller.is_busy(),
        timeout=15,
    )
    controller.shutdown()


def test_rapid_connect_ignored_while_busy(
    fake_client, credentials: Credentials, tmp_path, monkeypatch, scripted_ip_service
) -> None:
    from tests.conftest import make_vpn_service

    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    monkeypatch.setenv("FAKE_HS_MODE", "slow_connect")
    monkeypatch.setenv("FAKE_HS_SLOW", "0.5")
    controller = VpnController(
        service=make_vpn_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    controller.initialize()
    _wait_until(controller, lambda: bool(controller.locations), timeout=8)
    controller.select_location(controller.locations[0])
    controller.connect()
    _wait_until(
        controller,
        lambda: controller.machine.state in {VpnState.CONNECTING, VpnState.CONNECTED},
        timeout=3,
    )
    # Second connect should be rejected because worker busy / invalid state
    controller.connect()
    _wait_until(controller, lambda: controller.machine.state is VpnState.CONNECTED, timeout=10)
    controller.shutdown()
