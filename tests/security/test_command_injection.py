"""Security-focused tests."""

from __future__ import annotations

import pytest

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.cli.process_runner import ProcessRunner
from hotspotshield_gui.utils.errors import LocationUnavailableError

INJECTION_PAYLOADS = [
    "US; id",
    "US && id",
    "US|id",
    "US`id`",
    "$(id)",
    "US\nDE",
    "../../../etc/passwd",
    "US'\"",
]


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_connect_rejects_metacharacters(fake_client: HotspotShieldClient, payload: str) -> None:
    with pytest.raises(LocationUnavailableError):
        fake_client.connect(payload)


def test_command_uses_argument_vector(fake_hotspotshield, monkeypatch, tmp_path) -> None:
    """Ensure ProcessRunner never receives a shell string."""
    runner = ProcessRunner()
    seen: list[list[str]] = []
    original = runner.run

    def tracking(argv, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(list(argv))
        return original(argv, **kwargs)

    runner.run = tracking  # type: ignore[method-assign]
    client = HotspotShieldClient(runner, executable=str(fake_hotspotshield))
    client.status()
    assert seen
    assert isinstance(seen[0], list)
    assert all(isinstance(part, str) for part in seen[0])
    assert " " not in seen[0][0] or seen[0][0].endswith("hotspotshield")
