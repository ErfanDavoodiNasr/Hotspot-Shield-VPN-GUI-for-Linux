"""Public IP / network probing with multi-provider consensus."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import json
import logging
import socket
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from hotspotshield_gui.utils.errors import NetworkProbeError

logger = logging.getLogger("hotspotshield_gui.services.ip_service")

DEFAULT_ENDPOINTS: tuple[str, ...] = (
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/ip",
    "https://ipinfo.io/ip",
)


@dataclass(frozen=True)
class PublicIpInfo:
    ip: str
    city: str | None = None
    country: str | None = None
    org: str | None = None
    raw_source: str | None = None

    def display(self) -> str:
        parts = [f"IP: {self.ip}"]
        if self.city:
            parts.append(f"City: {self.city}")
        if self.country:
            parts.append(f"Country: {self.country}")
        return "\n".join(parts)

    def masked(self) -> str:
        return mask_ip(self.ip)


@dataclass(frozen=True)
class IpConsensusResult:
    agreed: PublicIpInfo | None
    samples: tuple[PublicIpInfo, ...] = ()
    inconclusive: bool = False
    reasons: tuple[str, ...] = ()


@dataclass
class IpService:
    """Query public IP using multiple endpoints with consensus."""

    endpoints: Sequence[str] = field(default_factory=lambda: list(DEFAULT_ENDPOINTS))
    timeout: float = 8.0
    min_agreement: int = 2

    def has_basic_connectivity(self, host: str = "1.1.1.1", port: int = 53) -> bool:
        try:
            with socket.create_connection((host, port), timeout=self.timeout):
                return True
        except OSError:
            try:
                with socket.create_connection(("8.8.8.8", 53), timeout=self.timeout):
                    return True
            except OSError:
                return False

    def lookup(self) -> PublicIpInfo:
        """Backward-compatible: return consensus IP or raise."""
        result = self.lookup_consensus()
        if result.agreed is None:
            raise NetworkProbeError(
                "; ".join(result.reasons) if result.reasons else "IP consensus inconclusive"
            )
        return result.agreed

    def lookup_consensus(self) -> IpConsensusResult:
        samples: list[PublicIpInfo] = []
        errors: list[str] = []

        def _one(url: str) -> PublicIpInfo | None:
            return self._fetch(url)

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(self.endpoints))) as pool:
            futures = {pool.submit(_one, url): url for url in self.endpoints}
            for fut in concurrent.futures.as_completed(futures, timeout=self.timeout + 2):
                url = futures[fut]
                try:
                    info = fut.result()
                    if info is not None:
                        samples.append(info)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{url}: {exc}")
                    logger.debug("IP lookup failed for %s: %s", url, exc)

        if not samples:
            raise NetworkProbeError("; ".join(errors) if errors else "No endpoints")

        counts = Counter(item.ip for item in samples)
        winner, votes = counts.most_common(1)[0]
        need = min(self.min_agreement, len(self.endpoints))
        if votes < need and len(samples) >= need:
            return IpConsensusResult(
                agreed=None,
                samples=tuple(samples),
                inconclusive=True,
                reasons=(f"providers_disagree:{dict(counts)}",),
            )
        if votes < need:
            # Fewer successful probes than desired — still return best effort marked inconclusive
            # only when a single probe exists and we wanted 2+.
            agreed = next(s for s in samples if s.ip == winner)
            return IpConsensusResult(
                agreed=agreed,
                samples=tuple(samples),
                inconclusive=len(samples) < need,
                reasons=("insufficient_providers",) if len(samples) < need else (),
            )
        agreed = next(s for s in samples if s.ip == winner)
        return IpConsensusResult(agreed=agreed, samples=tuple(samples), inconclusive=False)

    def _fetch(self, url: str) -> PublicIpInfo | None:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme == "https" or parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
            pass
        else:
            raise ValueError(f"Unsupported URL scheme: {url}")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "hotspotshield-gui/1.0",
                "Accept": "application/json,text/plain",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            body = response.read(65_536).decode("utf-8", errors="replace").strip()
        if not body:
            return None
        if body.startswith("{"):
            data = json.loads(body)
            ip = str(data.get("ip") or data.get("query") or "").strip()
            if not _valid_ip(ip):
                return None
            return PublicIpInfo(
                ip=str(ipaddress.ip_address(ip)),
                city=_optional_str(data.get("city")),
                country=_optional_str(data.get("country") or data.get("countryCode")),
                org=_optional_str(data.get("org") or data.get("isp")),
                raw_source=url,
            )
        candidate = body.split()[0]
        if not _valid_ip(candidate):
            return None
        return PublicIpInfo(ip=str(ipaddress.ip_address(candidate)), raw_source=url)


def mask_ip(value: str) -> str:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return "xxx"
    if isinstance(addr, ipaddress.IPv4Address):
        parts = str(addr).split(".")
        return ".".join([*parts[:3], "xxx"])
    text = str(addr)
    chunks = text.split(":")
    if len(chunks) >= 2:
        return ":".join([chunks[0], "xxxx", *(["xxxx"] * max(0, len(chunks) - 3)), "…"])
    return "xxxx:…"


def _valid_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text.strip())
        return True
    except ValueError:
        return False


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
