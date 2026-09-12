"""Authoritative VPN connection verification using multiple independent signals."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from hotspotshield_gui.cli.hotspotshield_client import HotspotShieldClient
from hotspotshield_gui.models.vpn_state import VpnState, VpnStatusInfo
from hotspotshield_gui.services.ip_service import IpConsensusResult, IpService, PublicIpInfo
from hotspotshield_gui.utils.errors import AppError, VerificationError

logger = logging.getLogger("hotspotshield_gui.services.connection_verifier")


class VerificationOutcome(str, Enum):
    VERIFIED_CONNECTED = "verified_connected"
    VERIFIED_DISCONNECTED = "verified_disconnected"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


@dataclass
class VerificationReport:
    outcome: VerificationOutcome
    cli_status: VpnStatusInfo | None = None
    baseline_ip: PublicIpInfo | None = None
    current_ip: PublicIpInfo | None = None
    ip_consensus: IpConsensusResult | None = None
    signals: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome in {
            VerificationOutcome.VERIFIED_CONNECTED,
            VerificationOutcome.VERIFIED_DISCONNECTED,
        }


class ConnectionVerifier:
    """Combine CLI status + independent egress IP signals.

    CLI text alone is never enough to claim the user is protected.
    """

    def __init__(
        self,
        client: HotspotShieldClient | None = None,
        ip_service: IpService | None = None,
    ) -> None:
        self.client = client or HotspotShieldClient()
        self.ip_service = ip_service or IpService()

    def capture_baseline(self) -> PublicIpInfo | None:
        try:
            result = self.ip_service.lookup_consensus()
            if result.inconclusive or result.agreed is None:
                return None
            return result.agreed
        except AppError as exc:
            logger.info("Baseline IP unavailable: %s", exc.technical)
            return None

    def verify_connected(
        self,
        *,
        expected_location: str | None = None,
        baseline: PublicIpInfo | None = None,
        require_ip_change: bool = True,
    ) -> VerificationReport:
        signals: list[str] = []
        reasons: list[str] = []
        status: VpnStatusInfo | None = None
        try:
            status = self.client.status()
        except AppError as exc:
            reasons.append(f"cli_status_unavailable:{exc.technical}")
            return VerificationReport(
                outcome=VerificationOutcome.FAILED,
                reasons=reasons,
                signals=signals,
            )

        if status.state is not VpnState.CONNECTED:
            reasons.append(f"cli_not_connected:{status.state.value}")
            return VerificationReport(
                outcome=VerificationOutcome.FAILED,
                cli_status=status,
                reasons=reasons,
                signals=signals,
            )
        signals.append("cli_connected")

        if expected_location:
            code = (status.connected_location_code or "").upper()
            if code and code != expected_location.strip().upper():
                reasons.append(f"location_mismatch:cli={code},expected={expected_location}")
            else:
                signals.append("cli_location_ok")

        consensus: IpConsensusResult | None = None
        current: PublicIpInfo | None = None
        try:
            consensus = self.ip_service.lookup_consensus()
            if consensus.inconclusive or consensus.agreed is None:
                reasons.append("ip_consensus_inconclusive")
            else:
                current = consensus.agreed
                signals.append("ip_consensus")
        except AppError as exc:
            reasons.append(f"ip_lookup_failed:{exc.technical}")

        if require_ip_change and baseline is not None and current is not None:
            if current.ip == baseline.ip:
                reasons.append("egress_ip_unchanged")
            else:
                signals.append("egress_ip_changed")

        # Connected claim requires CLI connected + usable consensus (or explicit
        # inconclusive when network probes are unavailable — still not "protected").
        if "cli_connected" in signals and "ip_consensus" in signals:
            if require_ip_change and baseline is not None and "egress_ip_changed" not in signals:
                return VerificationReport(
                    outcome=VerificationOutcome.INCONCLUSIVE,
                    cli_status=status,
                    baseline_ip=baseline,
                    current_ip=current,
                    ip_consensus=consensus,
                    signals=signals,
                    reasons=reasons,
                )
            return VerificationReport(
                outcome=VerificationOutcome.VERIFIED_CONNECTED,
                cli_status=status,
                baseline_ip=baseline,
                current_ip=current,
                ip_consensus=consensus,
                signals=signals,
                reasons=reasons,
            )

        if "cli_connected" in signals and not current:
            # CLI says connected but we could not independently measure egress.
            return VerificationReport(
                outcome=VerificationOutcome.INCONCLUSIVE,
                cli_status=status,
                baseline_ip=baseline,
                current_ip=current,
                ip_consensus=consensus,
                signals=signals,
                reasons=reasons or ["unable_to_verify_egress"],
            )

        return VerificationReport(
            outcome=VerificationOutcome.FAILED,
            cli_status=status,
            baseline_ip=baseline,
            current_ip=current,
            ip_consensus=consensus,
            signals=signals,
            reasons=reasons,
        )

    def verify_disconnected(
        self,
        *,
        previous_vpn_ip: str | None = None,
        baseline: PublicIpInfo | None = None,
    ) -> VerificationReport:
        signals: list[str] = []
        reasons: list[str] = []
        status: VpnStatusInfo | None = None
        try:
            status = self.client.status()
        except AppError as exc:
            reasons.append(f"cli_status_unavailable:{exc.technical}")
            return VerificationReport(
                outcome=VerificationOutcome.INCONCLUSIVE,
                reasons=reasons,
                signals=signals,
            )

        if status.state is VpnState.CONNECTED:
            reasons.append("cli_still_connected")
            return VerificationReport(
                outcome=VerificationOutcome.FAILED,
                cli_status=status,
                reasons=reasons,
                signals=signals,
            )
        if status.state is not VpnState.DISCONNECTED:
            reasons.append(f"cli_unexpected_state:{status.state.value}")
            return VerificationReport(
                outcome=VerificationOutcome.INCONCLUSIVE,
                cli_status=status,
                reasons=reasons,
                signals=signals,
            )
        signals.append("cli_disconnected")

        consensus: IpConsensusResult | None = None
        current: PublicIpInfo | None = None
        try:
            consensus = self.ip_service.lookup_consensus()
            if consensus.agreed is not None:
                current = consensus.agreed
                signals.append("ip_consensus")
                if previous_vpn_ip and current.ip == previous_vpn_ip:
                    reasons.append("still_on_vpn_egress_ip")
                elif previous_vpn_ip:
                    signals.append("left_vpn_egress_ip")
                if baseline is not None and current.ip == baseline.ip:
                    signals.append("returned_to_baseline_ip")
        except AppError as exc:
            reasons.append(f"ip_lookup_failed:{exc.technical}")

        if "cli_disconnected" in signals and "still_on_vpn_egress_ip" not in reasons:
            return VerificationReport(
                outcome=VerificationOutcome.VERIFIED_DISCONNECTED,
                cli_status=status,
                baseline_ip=baseline,
                current_ip=current,
                ip_consensus=consensus,
                signals=signals,
                reasons=reasons,
            )
        return VerificationReport(
            outcome=VerificationOutcome.INCONCLUSIVE,
            cli_status=status,
            baseline_ip=baseline,
            current_ip=current,
            ip_consensus=consensus,
            signals=signals,
            reasons=reasons,
        )

    def require_connected(self, **kwargs: object) -> VerificationReport:
        report = self.verify_connected(**kwargs)  # type: ignore[arg-type]
        if report.outcome is VerificationOutcome.VERIFIED_CONNECTED:
            return report
        raise VerificationError(
            "Unable to verify VPN connection.\n\n"
            "The VPN command finished, but independent checks could not confirm "
            "that your traffic is protected.",
            technical="; ".join(report.reasons) or report.outcome.value,
        )

    def require_disconnected(self, **kwargs: object) -> VerificationReport:
        report = self.verify_disconnected(**kwargs)  # type: ignore[arg-type]
        if report.outcome is VerificationOutcome.VERIFIED_DISCONNECTED:
            return report
        raise VerificationError(
            "Unable to verify disconnection.\n\n"
            "The tunnel state is uncertain. Refresh status or try Disconnect again.",
            technical="; ".join(report.reasons) or report.outcome.value,
        )
