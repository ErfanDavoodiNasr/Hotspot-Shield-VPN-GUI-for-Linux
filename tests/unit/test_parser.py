"""Location parser tests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hotspotshield_gui.cli.parser import filter_locations, parse_locations, parse_status
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.utils.errors import ParseError

SAMPLE = """Virtual locations:
CODE  NAME
US    United States
DE    Germany
USNY  United States - New York
FR    France
"""


def test_parse_normal_locations() -> None:
    locs = parse_locations(SAMPLE)
    assert [loc.code for loc in locs] == ["US", "DE", "USNY", "FR"]
    assert locs[0].name == "United States"


def test_parse_single_location() -> None:
    locs = parse_locations("CODE  NAME\nJP    Japan\n")
    assert len(locs) == 1
    assert locs[0].code == "JP"


def test_parse_empty_table() -> None:
    assert parse_locations("Virtual locations:\nCODE  NAME\n") == []


def test_parse_duplicates_deduped() -> None:
    locs = parse_locations("US United States\nUS United States Again\n")
    assert len(locs) == 1


def test_parse_unicode() -> None:
    locs = parse_locations("JP    日本\n")
    assert locs[0].name == "日本"


def test_parse_long_name() -> None:
    name = "X" * 500
    locs = parse_locations(f"ZZ    {name}\n")
    assert locs[0].name == name


def test_malformed_error_message() -> None:
    with pytest.raises(ParseError):
        parse_locations("Can't retrieve list of virtual locations.")


def test_filter_case_insensitive() -> None:
    locs = parse_locations(SAMPLE)
    assert [x.code for x in filter_locations(locs, "united")] == ["US", "USNY"]
    assert [x.code for x in filter_locations(locs, "UNITED")] == ["US", "USNY"]
    assert [x.code for x in filter_locations(locs, "  ger ")] == ["DE"]
    assert filter_locations(locs, "nonexistent-location") == []


def test_location_matches_whitespace() -> None:
    loc = Location("US", "United States")
    assert loc.matches_query("  us  ")
    assert loc.matches_query("States")


def test_parse_status_connected() -> None:
    info = parse_status(
        "VPN connection state : connected\nConnected location   : US  (United States)\n"
    )
    assert info.state is VpnState.CONNECTED
    assert info.connected_location_code == "US"


def test_parse_status_disconnected() -> None:
    info = parse_status("VPN connection state : disconnected\n")
    assert info.state is VpnState.DISCONNECTED


def test_parse_status_ambiguous_connected_word_is_unknown() -> None:
    for blob in (
        "Not connected\n",
        "Previously connected\n",
        "Failed while connected\n",
        "Could not verify connected state\n",
        "Disconnected\n",
    ):
        info = parse_status(blob)
        assert info.state is not VpnState.CONNECTED, blob


def test_parse_status_empty() -> None:
    with pytest.raises(ParseError):
        parse_status("   ")


@given(st.text(min_size=0, max_size=200))
@settings(max_examples=50)
def test_parse_locations_never_crashes(blob: str) -> None:
    try:
        parse_locations(blob)
    except ParseError:
        pass
