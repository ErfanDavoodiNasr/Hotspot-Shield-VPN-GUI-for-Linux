"""Stress / rapid-interaction tests (hermetic fake CLI)."""

from __future__ import annotations

import time
from pathlib import Path

from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.controllers.vpn_controller import VpnController
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials, SecretStore
from hotspotshield_gui.services.vpn_service import VpnService
from tests.conftest import make_vpn_service


def _wait(controller: VpnController, predicate, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.poll_events()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"timeout; state={controller.machine.state}")


def _fast_service(client, ip_service) -> VpnService:
    svc = make_vpn_service(client, ip_service)

    def fast_connect(location, credentials, *, progress=None, settle_seconds=0):
        return VpnService.connect(svc, location, credentials, progress=progress, settle_seconds=0)

    def fast_disconnect(*, progress=None, settle_seconds=0):
        return VpnService.disconnect(svc, progress=progress, settle_seconds=0)

    def fast_switch(location, credentials, *, progress=None):
        after = fast_disconnect(progress=progress)
        assert after.state is VpnState.DISCONNECTED
        try:
            svc.client.start_service()
        except Exception:
            pass
        return fast_connect(location, credentials, progress=progress)

    svc.connect = fast_connect  # type: ignore[method-assign]
    svc.disconnect = fast_disconnect  # type: ignore[method-assign]
    svc.switch_location = fast_switch  # type: ignore[method-assign]
    return svc


def test_connect_disconnect_cycles(
    fake_client, credentials: Credentials, tmp_path: Path, scripted_ip_service
) -> None:
    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    ctrl = VpnController(
        service=_fast_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    _wait(ctrl, lambda: bool(ctrl.locations) and ctrl.machine.state is not VpnState.INITIALIZING, timeout=20)
    loc = ctrl.locations[0]
    for _ in range(40):
        ctrl.select_location(loc)
        ctrl.connect()
        _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED and not ctrl.is_busy())
        ctrl.disconnect()
        _wait(ctrl, lambda: ctrl.machine.state is VpnState.DISCONNECTED and not ctrl.is_busy())
    ctrl.shutdown()


def test_rapid_search_filtering(
    fake_client, credentials: Credentials, tmp_path: Path, scripted_ip_service
) -> None:
    from hotspotshield_gui.cli.parser import filter_locations

    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    ctrl = VpnController(
        service=make_vpn_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    _wait(ctrl, lambda: bool(ctrl.locations) and ctrl.machine.state is not VpnState.INITIALIZING, timeout=20)
    queries = ["", "u", "un", "united", "UNITED", "ger", "  ger ", "zzz", "日本", "   "]
    for _ in range(100):
        for q in queries:
            filter_locations(ctrl.locations, q)
    ctrl.shutdown()


def test_rapid_location_switch(
    fake_client, credentials: Credentials, tmp_path: Path, scripted_ip_service
) -> None:
    store = SecretStore(config_dir=tmp_path)
    store.save(credentials)
    ctrl = VpnController(
        service=_fast_service(fake_client, scripted_ip_service),
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    _wait(ctrl, lambda: bool(ctrl.locations) and len(ctrl.locations) >= 2 and ctrl.machine.state is not VpnState.INITIALIZING, timeout=20)
    a, b = ctrl.locations[0], ctrl.locations[1]
    ctrl.select_location(a)
    ctrl.connect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED)
    for i in range(20):
        target = b if i % 2 == 0 else a
        ctrl.switch_location(target)
        _wait(
            ctrl,
            lambda t=target: ctrl.machine.state is VpnState.CONNECTED
            and not ctrl.is_busy()
            and ctrl.status_info is not None
            and ctrl.status_info.connected_location_code == t.code,
        )
    ctrl.disconnect()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.DISCONNECTED)
    ctrl.shutdown()
