"""High-level VPN operations."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnState, VpnStatusInfo
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.services.ip_service import IpService, PublicIpInfo
from hotspotshield_gui.utils.errors import (
    AppError,
    ConnectError,
    DisconnectError,
    SwitchLocationError,
)

logger = logging.getLogger("hotspotshield_gui.services.vpn_service")

ProgressCallback = Callable[[str], None]


class VpnService:
    """Orchestrates CLI operations used by the controller."""

    def __init__(
        self,
        client: HotspotShieldClient | None = None,
        ip_service: IpService | None = None,
    ) -> None:
        self.client = client or HotspotShieldClient()
        self.ip_service = ip_service or IpService()

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
        _progress(progress, "Starting VPN service…")
        try:
            self.client.start_service()
        except AppError as exc:
            logger.debug("start_service: %s", exc.technical)
        _progress(progress, f"Connecting to {code}…")
        info = self.client.connect(code)
        time.sleep(max(0.0, settle_seconds))
        try:
            info = self.client.status()
        except AppError:
            pass
        if info.state is not VpnState.CONNECTED:
            # Some CLI builds report connected slightly later.
            for _ in range(5):
                time.sleep(1.0)
                info = self.client.status()
                if info.state is VpnState.CONNECTED:
                    break
            else:
                raise ConnectError(f"VPN did not reach connected state (was {info.state.value})")
        return info

    def disconnect(
        self,
        *,
        progress: ProgressCallback | None = None,
        settle_seconds: float = 1.0,
    ) -> VpnStatusInfo:
        _progress(progress, "Disconnecting…")
        info = self.client.disconnect()
        time.sleep(max(0.0, settle_seconds))
        try:
            info = self.client.status()
        except AppError:
            pass
        if info.state not in {VpnState.DISCONNECTED, VpnState.ERROR}:
            for _ in range(5):
                time.sleep(1.0)
                info = self.client.status()
                if info.state is VpnState.DISCONNECTED:
                    break
            else:
                raise DisconnectError(f"VPN still in state {info.state.value}")
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
        except DisconnectError as exc:
            # Only continue if we are actually disconnected.
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


def _progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)
