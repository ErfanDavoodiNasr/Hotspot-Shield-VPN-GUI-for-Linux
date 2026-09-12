"""Network service facade."""

from __future__ import annotations

from hotspotshield_gui.services.ip_service import IpService, PublicIpInfo


class NetworkService:
    """Thin wrapper retained for architectural separation / future probes."""

    def __init__(self, ip_service: IpService | None = None) -> None:
        self.ip_service = ip_service or IpService()

    def public_ip(self) -> PublicIpInfo:
        return self.ip_service.lookup()

    def online(self) -> bool:
        return self.ip_service.has_basic_connectivity()
