"""Domain and user-facing error types with actionable copy."""

from __future__ import annotations


def _classify_cli_text(technical: str | None) -> str | None:
    if not technical:
        return None
    t = technical.lower()
    if "not signed" in t or ("signin" in t and "try" in t):
        return (
            "You are not signed in.\n\n"
            "Open Account… and enter your Hotspot Shield Premium email and password, then try again."
        )
    if "invalid" in t or "incorrect" in t or "wrong" in t:
        return (
            "Sign-in failed.\n\n"
            "Check your email and password, then try again. "
            "A Premium Hotspot Shield account is required."
        )
    if "internet" in t or "network" in t or "no route" in t:
        return (
            "No internet connection detected.\n\n"
            "Check your Wi‑Fi or cable connection, then try again."
        )
    if "unexpected location" in t or "unavailable" in t:
        return (
            "That location is not available right now.\n\n"
            "Choose a different location from the list and try again."
        )
    if "already established" in t:
        return (
            "The VPN is already connected.\n\n"
            "Disconnect first if you want to change location, or refresh status."
        )
    if "journal" in t or "can't establish" in t or "can't start" in t:
        return (
            "Hotspot Shield could not start the VPN.\n\n"
            "Make sure the Hotspot Shield CLI is installed and working, "
            "then try again. If it keeps failing, restart your computer."
        )
    if "timeout" in t or "timed out" in t:
        return (
            "The operation took too long.\n\n"
            "Check your internet connection and try again."
        )
    return None


class AppError(Exception):
    """Base application error with a user-safe message."""

    def __init__(
        self,
        user_message: str,
        *,
        technical: str | None = None,
        classify: bool = True,
    ) -> None:
        if classify:
            classified = _classify_cli_text(technical)
            message = classified or user_message
        else:
            message = user_message
        super().__init__(message)
        self.user_message = message
        self.technical = technical or user_message


class CliNotFoundError(AppError):
    def __init__(self, path: str = "hotspotshield") -> None:
        super().__init__(
            "Hotspot Shield is not installed on this computer.\n\n"
            "Install the official Hotspot Shield Linux package, then reopen this app.\n"
            "On Ubuntu/Debian you can install the .deb from your Hotspot Shield account page.",
            technical=f"Executable not found: {path}",
            classify=False,
        )


class CliTimeoutError(AppError):
    def __init__(self, command: str) -> None:
        cmd = command.lower()
        if "location" in cmd:
            user = (
                "Loading locations timed out.\n\n"
                "Check your internet connection and tap Retry."
            )
        elif "account" in cmd or "signin" in cmd:
            user = (
                "Sign-in timed out.\n\n"
                "Check your internet connection and try again."
            )
        elif "status" in cmd:
            user = (
                "Checking VPN status timed out.\n\n"
                "Check your internet connection and refresh status."
            )
        else:
            user = (
                "The operation timed out.\n\n"
                "Check your internet connection and try again."
            )
        super().__init__(user, technical=f"Timed out running: {command}", classify=False)


class CliPermissionError(AppError):
    def __init__(self, path: str) -> None:
        super().__init__(
            "Permission denied when running Hotspot Shield.\n\n"
            "Try relaunching the app, or reinstall the Hotspot Shield CLI.",
            technical=f"Permission denied: {path}",
        )


class AuthenticationError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Unable to sign in.\n\n"
            "Check your email and password. A Premium Hotspot Shield account is required.",
            technical=technical or "Authentication failed",
        )


class LocationListError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Unable to load VPN locations.\n\n"
            "Sign in under Account…, check your internet connection, then tap Retry.",
            technical=technical or "Location list failed",
        )


class ParseError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Hotspot Shield sent an unexpected response.\n\n"
            "Try refreshing status. If this keeps happening, update or reinstall the CLI.",
            technical=technical or "Parse error",
        )


class ConnectError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Unable to connect.\n\n"
            "Check your internet connection, pick another location, and try again.",
            technical=technical or "Connect failed",
        )


class DisconnectError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Unable to disconnect.\n\n"
            "Try again, or use Refresh status. If the VPN stays on, restart Hotspot Shield.",
            technical=technical or "Disconnect failed",
        )


class NetworkProbeError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "No internet connection detected.\n\n"
            "Check your Wi‑Fi or cable connection, then try again.",
            technical=technical or "Network probe failed",
        )


class LocationUnavailableError(AppError):
    def __init__(self, code: str) -> None:
        super().__init__(
            "The selected location is unavailable.\n\n"
            "Choose a different location from the list and try again.",
            technical=f"Location unavailable: {code}",
        )


class SwitchLocationError(AppError):
    def __init__(self, technical: str | None = None) -> None:
        super().__init__(
            "Unable to change location.\n\n"
            "The current connection could not be closed. Disconnect, then connect to the new location.",
            technical=technical or "Switch failed",
        )
