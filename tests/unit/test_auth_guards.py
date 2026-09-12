"""Regression: do not treat CLI environment errors as authenticated."""

from __future__ import annotations

import pytest

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.cli.process_runner import CommandResult, ProcessRunner
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.services.vpn_service import VpnService
from hotspotshield_gui.utils.errors import AuthenticationError


class _FakeRunner(ProcessRunner):
    def __init__(self, mapping: dict[tuple[str, ...], CommandResult]) -> None:
        super().__init__()
        self.mapping = mapping

    def run(self, argv, **kwargs):  # type: ignore[no-untyped-def]
        key = tuple(argv[1:])  # drop executable
        if key in self.mapping:
            return self.mapping[key]
        return CommandResult(argv=tuple(argv), returncode=0, stdout="", stderr="", duration_seconds=0)


def test_ensure_signed_in_rejects_environment_noise() -> None:
    runner = _FakeRunner(
        {
            ("account", "status"): CommandResult(
                argv=("hotspotshield", "account", "status"),
                returncode=1,
                stdout="",
                stderr="unable to get data about FS devices\ncan't get device uuid\n",
                duration_seconds=0.1,
            ),
            ("account", "signin"): CommandResult(
                argv=("hotspotshield", "account", "signin"),
                returncode=1,
                stdout="",
                stderr="unable to get data about FS devices\n",
                duration_seconds=0.1,
            ),
        }
    )
    client = HotspotShieldClient(runner, executable="hotspotshield")
    # Bypass availability check
    client.available = lambda: True  # type: ignore[method-assign]
    service = VpnService(client)
    with pytest.raises(AuthenticationError):
        service.ensure_signed_in(Credentials("u@e.com", "pw"))
