"""User-facing error message quality."""

from __future__ import annotations

from hotspotshield_gui.utils.errors import (
    AuthenticationError,
    CliTimeoutError,
    ConnectError,
    LocationListError,
)


def test_timeout_message_varies_by_command() -> None:
    assert "locations" in CliTimeoutError("hotspotshield locations").user_message.lower()
    assert "sign" in CliTimeoutError("hotspotshield account signin").user_message.lower()


def test_connect_error_is_actionable() -> None:
    err = ConnectError("can't establish VPN connection")
    assert "internet" in err.user_message.lower() or "try again" in err.user_message.lower()
    assert "traceback" not in err.user_message.lower()
    assert "exit code" not in err.user_message.lower()


def test_auth_error_mentions_premium() -> None:
    err = AuthenticationError("Invalid username or password")
    assert "premium" in err.user_message.lower() or "password" in err.user_message.lower()


def test_location_list_error_suggests_retry() -> None:
    err = LocationListError("failed")
    assert "retry" in err.user_message.lower() or "sign in" in err.user_message.lower()
