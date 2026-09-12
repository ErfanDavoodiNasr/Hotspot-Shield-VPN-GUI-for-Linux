"""Hotspot Shield CLI client."""

from __future__ import annotations

import logging
import shutil

from hotspotshield_gui.cli.parser import parse_locations, parse_status
from hotspotshield_gui.cli.process_runner import CommandResult, ProcessRunner
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnStatusInfo
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.utils.errors import (
    AppError,
    AuthenticationError,
    CliNotFoundError,
    ConnectError,
    DisconnectError,
    LocationListError,
    LocationUnavailableError,
)

logger = logging.getLogger("hotspotshield_gui.cli.hotspotshield_client")


class HotspotShieldClient:
    """Typed wrapper around the ``hotspotshield`` executable."""

    def __init__(
        self,
        runner: ProcessRunner | None = None,
        *,
        executable: str | None = None,
    ) -> None:
        self.runner = runner or ProcessRunner()
        self.executable = executable or self.runner.which("hotspotshield") or "hotspotshield"

    def available(self) -> bool:
        path = shutil.which(self.executable) or self.runner.which(self.executable)
        return path is not None

    def ensure_available(self) -> None:
        if not self.available():
            raise CliNotFoundError(self.executable)

    def _cmd(self, *args: str) -> list[str]:
        return [self.executable, *args]

    def start_service(self, *, timeout: float = 30.0) -> CommandResult:
        return self.runner.run(self._cmd("start"), timeout=timeout)

    def stop_service(self, *, timeout: float = 30.0) -> CommandResult:
        return self.runner.run(self._cmd("stop"), timeout=timeout)

    def status(self, *, timeout: float = 30.0) -> VpnStatusInfo:
        self.ensure_available()
        result = self.runner.run(self._cmd("status"), timeout=timeout)
        text = result.combined
        if not text.strip() and result.returncode != 0:
            raise AppError(
                "Hotspot Shield returned an unexpected response.",
                technical=f"status exit {result.returncode}",
            )
        return parse_status(text or result.stdout)

    def locations(self, *, timeout: float = 60.0) -> list[Location]:
        self.ensure_available()
        result = self.runner.run(self._cmd("locations"), timeout=timeout)
        text = result.stdout or result.combined
        if result.returncode != 0 and not text.strip():
            raise LocationListError(f"exit {result.returncode}")
        try:
            return parse_locations(text)
        except Exception as exc:
            raise LocationListError(str(exc)) from exc

    def account_status(self, *, timeout: float = 30.0) -> str:
        result = self.runner.run(self._cmd("account", "status"), timeout=timeout)
        return result.combined

    def sign_in(self, credentials: Credentials, *, timeout: float = 60.0) -> None:
        self.ensure_available()
        if not credentials.is_complete():
            raise AuthenticationError("Missing username or password")

        # Interactive CLI expects Username / Password prompts.
        payload = f"{credentials.username}\n{credentials.password}\n"
        result = self.runner.run(
            self._cmd("account", "signin"),
            timeout=timeout,
            input_text=payload,
        )
        combined = result.combined.lower()
        failure_markers = (
            "invalid",
            "failed",
            "incorrect",
            "denied",
            "error",
            "can't",
            "cannot",
            "unable",
            "not signed",
            "root user",
            "unprivileged",
            "device uuid",
            "environment information",
        )
        if result.returncode != 0 or any(m in combined for m in failure_markers):
            # Some builds print little on success; verify with account status.
            verify = self.account_status(timeout=timeout)
            verify_l = verify.lower()
            if (
                "signed in" not in verify_l
                or "not signed" in verify_l
                or any(m in verify_l for m in ("root user", "device uuid", "unable"))
                or result.returncode != 0
            ):
                raise AuthenticationError(result.combined or verify)
        logger.info("Sign-in completed")

    def sign_out(self, *, timeout: float = 30.0) -> CommandResult:
        return self.runner.run(self._cmd("account", "signout"), timeout=timeout)

    def connect(self, location_code: str, *, timeout: float = 90.0) -> VpnStatusInfo:
        self.ensure_available()
        code = location_code.strip()
        # Codes are short alphanumeric tokens (e.g. US, USNY). Reject anything else.
        if not code or not code.isalnum():
            raise LocationUnavailableError(location_code)

        result = self.runner.run(self._cmd("connect", code), timeout=timeout)
        combined = result.combined.lower()
        if "already established" in combined:
            logger.info("VPN already connected")
            try:
                return self.status(timeout=min(timeout, 30.0))
            except AppError:
                from hotspotshield_gui.models.vpn_state import VpnState

                return VpnStatusInfo(state=VpnState.CONNECTED, connected_location_code=code)
        if (
            result.returncode != 0
            or "can't establish" in combined
            or "unexpected location" in combined
        ):
            raise ConnectError(result.combined or f"exit {result.returncode}")
        # Prefer authoritative status after connect.
        try:
            return self.status(timeout=min(timeout, 30.0))
        except AppError as exc:
            if result.ok:
                from hotspotshield_gui.models.vpn_state import VpnState

                return VpnStatusInfo(state=VpnState.CONNECTED, connected_location_code=code)
            raise ConnectError(result.combined) from exc

    def disconnect(self, *, timeout: float = 60.0) -> VpnStatusInfo:
        self.ensure_available()
        result = self.runner.run(self._cmd("disconnect"), timeout=timeout)
        combined = result.combined.lower()
        if result.returncode != 0 and "already" not in combined:
            raise DisconnectError(result.combined or f"exit {result.returncode}")
        try:
            return self.status(timeout=min(timeout, 30.0))
        except AppError:
            from hotspotshield_gui.models.vpn_state import VpnState

            return VpnStatusInfo(state=VpnState.DISCONNECTED)

    def help_text(self, *, timeout: float = 15.0) -> str:
        result = self.runner.run(self._cmd("help"), timeout=timeout)
        return result.combined
