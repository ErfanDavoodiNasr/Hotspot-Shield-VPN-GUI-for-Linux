"""Public IP / network probing."""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass

from hotspotshield_gui.utils.errors import NetworkProbeError

logger = logging.getLogger("hotspotshield_gui.services.ip_service")

DEFAULT_ENDPOINTS: tuple[str, ...] = (
    "https://ipinfo.io/json",
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/ip",
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


class IpService:
    """Query public IP using multiple endpoints (no single point of failure)."""

    def __init__(
        self,
        endpoints: Sequence[str] | None = None,
        *,
        timeout: float = 8.0,
    ) -> None:
        self.endpoints = list(endpoints or DEFAULT_ENDPOINTS)
        self.timeout = timeout

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
        errors: list[str] = []
        for url in self.endpoints:
            try:
                info = self._fetch(url)
                if info is not None:
                    return info
            except Exception as exc:  # noqa: BLE001 — collect and continue
                errors.append(f"{url}: {exc}")
                logger.debug("IP lookup failed for %s: %s", url, exc)
        raise NetworkProbeError("; ".join(errors) if errors else "No endpoints")

    def _fetch(self, url: str) -> PublicIpInfo | None:
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"Unsupported URL scheme: {url}")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "hotspotshield-gui/1.0",
                "Accept": "application/json,text/plain",
            },
            method="GET",
        )  # noqa: S310
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            body = response.read(65_536).decode("utf-8", errors="replace").strip()
        if not body:
            return None
        if body.startswith("{"):
            data = json.loads(body)
            ip = str(data.get("ip") or data.get("query") or "").strip()
            if not ip:
                return None
            return PublicIpInfo(
                ip=ip,
                city=_optional_str(data.get("city")),
                country=_optional_str(data.get("country") or data.get("countryCode")),
                org=_optional_str(data.get("org") or data.get("isp")),
                raw_source=url,
            )
        # Plain-text IP body (ifconfig.me/ip)
        if _looks_like_ip(body):
            return PublicIpInfo(ip=body.split()[0], raw_source=url)
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_ip(text: str) -> bool:
    candidate = text.split()[0]
    # IPv4 or IPv6-ish
    if candidate.count(".") == 3:
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in candidate.split("."))
    return ":" in candidate and all(c.isalnum() or c in ":." for c in candidate)
