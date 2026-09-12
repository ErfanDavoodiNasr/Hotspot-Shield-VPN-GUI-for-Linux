"""Connection verifier unit tests."""

from __future__ import annotations

from hotspotshield_gui.models.vpn_state import VpnState, VpnStatusInfo
from hotspotshield_gui.services.connection_verifier import (
    ConnectionVerifier,
    VerificationOutcome,
)
from hotspotshield_gui.services.ip_service import IpConsensusResult, PublicIpInfo


class _StubClient:
    def __init__(self, status: VpnStatusInfo) -> None:
        self._status = status

    def status(self, *, timeout: float = 30.0) -> VpnStatusInfo:
        return self._status


class _StubIp:
    def __init__(self, ip: str) -> None:
        self.ip = ip

    def lookup_consensus(self) -> IpConsensusResult:
        info = PublicIpInfo(ip=self.ip)
        return IpConsensusResult(agreed=info, samples=(info, info), inconclusive=False)


def test_verify_connected_requires_ip_change() -> None:
    client = _StubClient(
        VpnStatusInfo(state=VpnState.CONNECTED, connected_location_code="US")
    )
    verifier = ConnectionVerifier(client, _StubIp("198.51.100.20"))  # type: ignore[arg-type]
    baseline = PublicIpInfo(ip="203.0.113.10")
    report = verifier.verify_connected(
        expected_location="US", baseline=baseline, require_ip_change=True
    )
    assert report.outcome is VerificationOutcome.VERIFIED_CONNECTED


def test_verify_connected_inconclusive_when_ip_unchanged() -> None:
    client = _StubClient(VpnStatusInfo(state=VpnState.CONNECTED, connected_location_code="US"))
    verifier = ConnectionVerifier(client, _StubIp("203.0.113.10"))  # type: ignore[arg-type]
    baseline = PublicIpInfo(ip="203.0.113.10")
    report = verifier.verify_connected(baseline=baseline, require_ip_change=True)
    assert report.outcome is VerificationOutcome.INCONCLUSIVE


def test_mask_ip() -> None:
    from hotspotshield_gui.services.ip_service import mask_ip

    assert mask_ip("203.0.113.45") == "203.0.113.xxx"
