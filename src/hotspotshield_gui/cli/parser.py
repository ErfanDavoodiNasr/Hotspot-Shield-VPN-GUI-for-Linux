"""Parsers for Hotspot Shield CLI output."""

from __future__ import annotations

import re
from collections.abc import Iterable

from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnState, VpnStatusInfo
from hotspotshield_gui.utils.errors import ParseError

_HEADER_RE = re.compile(
    r"^(virtual\s*locations?:?|code(\s+name)?|name|location|---+|\s*)$",
    re.I,
)
_HEADER_CODES = frozenset({"CODE", "NAME", "LOCATION", "VIRTUAL", "LOCATIONS"})
_LOCATION_RE = re.compile(r"^([A-Za-z0-9]{2,12})\s{1,}(.+?)\s*$")
_STATE_RE = re.compile(
    r"VPN connection state\s*:\s*(connected|disconnected|connecting|disconnecting|"
    r"intermediate|unknown|[A-Za-z ]+)",
    re.I,
)
_CONNECTED_LOC_RE = re.compile(
    r"Connected location\s*:\s*([A-Za-z0-9]+)\s*(?:\((.+?)\))?",
    re.I,
)
_KV_RE = re.compile(r"^([^:\n]+?)\s*:\s*(.+?)\s*$")


def parse_locations(output: str) -> list[Location]:
    """Parse ``hotspotshield locations`` output into Location objects."""
    if output is None:
        raise ParseError("locations output was None")

    locations: list[Location] = []
    seen: set[str] = set()
    malformed = 0
    saw_table_header = False

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _HEADER_RE.match(line):
            if line.upper().startswith("CODE"):
                saw_table_header = True
            continue
        match = _LOCATION_RE.match(line)
        if not match:
            # Tolerate decorative separators / notes.
            if re.search(r"[A-Za-z]", line):
                malformed += 1
            continue
        code, name = match.group(1), match.group(2).strip()
        # Reject lines that look like prose rather than a location table.
        if " " in code:
            malformed += 1
            continue
        key = code.upper()
        if key in _HEADER_CODES or key in seen:
            continue
        seen.add(key)
        try:
            locations.append(Location(code=code, name=name))
        except ValueError:
            malformed += 1

    if not locations and output.strip():
        # Header-only tables are valid (zero locations).
        if saw_table_header or _HEADER_RE.match(output.strip().splitlines()[0]):
            return []
        lowered = output.lower()
        if "can't" in lowered or "not signed" in lowered or "failed" in lowered:
            raise ParseError(output.strip()[:300])
        raise ParseError("Could not parse any locations from CLI output")

    return locations


def parse_status(output: str) -> VpnStatusInfo:
    """Parse ``hotspotshield status`` output."""
    if not output or not output.strip():
        raise ParseError("Empty status output")

    details: dict[str, str] = {}
    for line in output.splitlines():
        kv = _KV_RE.match(line.strip())
        if kv:
            details[kv.group(1).strip()] = kv.group(2).strip()

    state_match = _STATE_RE.search(output)
    raw_token = state_match.group(1).strip().lower() if state_match else None
    state = _map_state_token(raw_token, output)

    loc_code: str | None = None
    loc_name: str | None = None
    loc_match = _CONNECTED_LOC_RE.search(output)
    if loc_match:
        loc_code = loc_match.group(1)
        loc_name = loc_match.group(2)

    return VpnStatusInfo(
        state=state,
        connected_location_code=loc_code,
        connected_location_name=loc_name,
        raw_state_token=raw_token,
        details=details,
    )


def _map_state_token(token: str | None, full: str) -> VpnState:
    text = (token or "").strip().lower()
    blob = full.lower()
    if text in {"connected"} or "vpn connection state : connected" in blob:
        return VpnState.CONNECTED
    if text in {"disconnected"} or "vpn connection state : disconnected" in blob:
        return VpnState.DISCONNECTED
    if text in {"connecting"}:
        return VpnState.CONNECTING
    if text in {"disconnecting"}:
        return VpnState.DISCONNECTING
    if "intermediate" in text:
        # Intermediate states are treated as connecting for UI purposes.
        return VpnState.CONNECTING
    if "connected" in blob and "disconnected" not in blob:
        return VpnState.CONNECTED
    if "disconnected" in blob:
        return VpnState.DISCONNECTED
    return VpnState.ERROR


def filter_locations(locations: Iterable[Location], query: str) -> list[Location]:
    return [loc for loc in locations if loc.matches_query(query)]
