"""Startup must not claim Connected from CLI text alone."""

from __future__ import annotations

import time
from pathlib import Path

from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.controllers.vpn_controller import VpnController
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import SecretStore
from hotspotshield_gui.services.connection_verifier import (
    ConnectionVerifier,
    VerificationOutcome,
    VerificationReport,
)
from tests.support.factories import make_vpn_service


def _wait(controller: VpnController, predicate, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.poll_events()
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"timeout waiting; state={controller.machine.state}")


def test_startup_connected_without_verification_is_unknown(fake_client, scripted_ip_service, tmp_path: Path) -> None:
    """CLI reports connected, but verifier fails → UNKNOWN (not Connected)."""
    fake_client.connect("US")  # establish fake connected status
    store = SecretStore(config_dir=tmp_path / "cfg")
    service = make_vpn_service(fake_client, scripted_ip_service)

    class _FailingVerifier(ConnectionVerifier):
        def verify_connected(self, **kwargs):  # type: ignore[no-untyped-def]
            return VerificationReport(
                outcome=VerificationOutcome.FAILED,
                reasons=["forced_failure"],
            )

    service.verifier = _FailingVerifier(fake_client, scripted_ip_service)
    ctrl = VpnController(
        service=service,
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    _wait(
        ctrl,
        lambda: ctrl.machine.state in {VpnState.UNKNOWN, VpnState.DISCONNECTED, VpnState.CONNECTED}
        and not ctrl.is_busy(),
    )
    assert ctrl.machine.state is VpnState.UNKNOWN
    assert ctrl.status_info is not None
    assert ctrl.status_info.verified is False


def test_startup_connected_with_verification_is_connected(fake_client, scripted_ip_service, tmp_path: Path) -> None:
    fake_client.connect("US")
    # Scripted IP: call 0 baseline-ish, but require_ip_change=False on startup.
    store = SecretStore(config_dir=tmp_path / "cfg")
    service = make_vpn_service(fake_client, scripted_ip_service)
    ctrl = VpnController(
        service=service,
        secret_store=store,
        settings_repo=SettingsRepository(store),
    )
    ctrl.initialize()
    _wait(ctrl, lambda: ctrl.machine.state is VpnState.CONNECTED and not ctrl.is_busy())
    assert ctrl.status_info is not None
    assert ctrl.status_info.verified is True
