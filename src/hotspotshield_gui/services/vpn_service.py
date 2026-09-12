"""High-level VPN operations with authoritative verification."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnState, VpnStatusInfo
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.services.connection_verifier import (
    ConnectionVerifier,
    VerificationOutcome,
)
from hotspotshield_gui.services.ip_service import IpService, PublicIpInfo
from hotspotshield_gui.utils.errors import (
    AppError,
    ConnectError,
    DisconnectError,
    SwitchLocationError,
    VerificationError,
)

logger = logging.getLogger("hotspotshield_gui.services.vpn_service")

ProgressCallback = Callable[[str], None]


class VpnService:
    """Orchestrates CLI operations used by the controller."""

    def __init__(
        self,
        client: HotspotShieldClient | None = None,
        ip_service: IpService | None = None,
        verifier: ConnectionVerifier | None = None,
        *,
        verify_egress: bool = True,
    ) -> None:
        self.client = client or HotspotShieldClient()
        self.ip_service = ip_service or IpService()
        self.verifier = verifier or ConnectionVerifier(self.client, self.ip_service)
        self.verify_egress = verify_egress
        self._baseline_ip: PublicIpInfo | None = None
        self._last_vpn_ip: str | None = None

    def cli_available(self) -> bool:
        return self.client.available()

    def refresh_status(self) -> VpnStatusInfo:
        return self.client.status()

    def list_locations(self) -> list[Location]:
        return self.client.locations()

    def ensure_signed_in(self, credentials: Credentials, progress: ProgressCallback | None = None) -> None:
        _progress(progress, "Authenticating…")
        try:
            account = self.client.account_status()
            lowered = account.lower()
            looks_signed_in = (
                account.strip()
                and "not signed" not in lowered
                and "signed in" in lowered
            )
            if looks_signed_in:
                logger.info("Already signed in")
                return
        except AppError:
            pass
        self.client.sign_in(credentials)

    def connect(
        self,
        location: Location | str,
        credentials: Credentials,
        *,
        progress: ProgressCallback | None = None,
        settle_seconds: float = 1.5,
    ) -> VpnStatusInfo:
        code = location.code if isinstance(location, Location) else location
        _progress(progress, "Authenticating…")
        self.ensure_signed_in(credentials, progress=progress)

        if self.verify_egress:
            _progress(progress, "Measuring public IP…")
            self._baseline_ip = self.verifier.capture_baseline()

        _progress(progress, "Starting VPN service…")
        try:
            self.client.start_service()
        except AppError as exc:
            logger.debug("start_service: %s", exc.technical)
        _progress(progress, f"Connecting to {code}…")
        info = self.client.connect(code)
        time.sleep(max(0.0, settle_seconds))
        info = self._wait_cli_state(VpnState.CONNECTED, progress=progress)

        _progress(progress, "Verifying connection…")
        if self.verify_egress:
            report = self.verifier.verify_connected(
                expected_location=code,
                baseline=self._baseline_ip,
                require_ip_change=self._baseline_ip is not None,
            )
            if report.outcome is VerificationOutcome.VERIFIED_CONNECTED:
                info = report.cli_status or info
                info.verified = True
                if report.current_ip is not None:
                    self._last_vpn_ip = report.current_ip.ip
                return info
            if report.outcome is VerificationOutcome.INCONCLUSIVE:
                raise VerificationError(
                    "Unable to verify VPN connection.\n\n"
                    "Hotspot Shield reported connected, but independent network checks "
                    "could not confirm protection.",
                    technical="; ".join(report.reasons),
                )
            raise ConnectError("; ".join(report.reasons) or "verification failed")
        if info.state is not VpnState.CONNECTED:
            raise ConnectError(f"VPN did not reach connected state (was {info.state.value})")
        info.verified = False
        return info

    def disconnect(
        self,
        *,
        progress: ProgressCallback | None = None,
        settle_seconds: float = 1.0,
        skip_verify: bool = False,
    ) -> VpnStatusInfo:
        _progress(progress, "Disconnecting…")
        previous = self._last_vpn_ip
        info = self.client.disconnect()
        time.sleep(max(0.0, settle_seconds))
        info = self._wait_cli_state(VpnState.DISCONNECTED, progress=progress, allow_error=True)

        _progress(progress, "Verifying disconnection…")
        if self.verify_egress and not skip_verify:
            report = self.verifier.verify_disconnected(
                previous_vpn_ip=previous,
                baseline=self._baseline_ip,
            )
            if report.outcome is VerificationOutcome.VERIFIED_DISCONNECTED:
                info = report.cli_status or info
                info.verified = True
                self._last_vpn_ip = None
                return info
            raise VerificationError(
                "Unable to verify disconnection.\n\n"
                "Tunnel state is uncertain. Refresh status or try again.",
                technical="; ".join(report.reasons),
            )
        if info.state not in {VpnState.DISCONNECTED, VpnState.ERROR}:
            raise DisconnectError(f"VPN still in state {info.state.value}")
        info.verified = False
        self._last_vpn_ip = None
        return info

    def switch_location(
        self,
        location: Location | str,
        credentials: Credentials,
        *,
        progress: ProgressCallback | None = None,
    ) -> VpnStatusInfo:
        _progress(progress, "Changing location…")
        try:
            after = self.disconnect(progress=progress, settle_seconds=1.0)
        except (DisconnectError, VerificationError) as exc:
            try:
                after = self.client.status()
            except AppError as status_exc:
                raise SwitchLocationError(exc.technical) from status_exc
            if after.state is not VpnState.DISCONNECTED:
                raise SwitchLocationError(exc.technical) from exc
        if after.state is not VpnState.DISCONNECTED:
            raise SwitchLocationError(f"Still in state {after.state.value} after disconnect")
        _progress(progress, "Starting VPN service…")
        try:
            self.client.start_service()
        except AppError:
            pass
        return self.connect(location, credentials, progress=progress, settle_seconds=1.5)

    def lookup_ip(self) -> PublicIpInfo | None:
        try:
            return self.ip_service.lookup()
        except AppError as exc:
            logger.warning("IP lookup failed: %s", exc.technical)
            return None

    def _wait_cli_state(
        self,
        wanted: VpnState,
        *,
        progress: ProgressCallback | None = None,
        allow_error: bool = False,
        attempts: int = 5,
    ) -> VpnStatusInfo:
        info = self.client.status()
        if info.state is wanted:
            return info
        for _ in range(attempts):
            time.sleep(1.0)
            info = self.client.status()
            if info.state is wanted:
                return info
            if allow_error and info.state is VpnState.ERROR and wanted is VpnState.DISCONNECTED:
                return info
        if wanted is VpnState.CONNECTED:
            raise ConnectError(f"VPN did not reach connected state (was {info.state.value})")
        raise DisconnectError(f"VPN still in state {info.state.value}")


def _progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)
