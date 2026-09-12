#!/usr/bin/env python3
"""Deterministic fake Hotspot Shield CLI for hermetic tests.

Control behavior with environment variables:

  FAKE_HS_MODE=success|auth_failure|timeout|malformed_output|network_failure|
               empty_locations|slow_connect|disconnect_failure|permission_denied|
               missing_executable
  FAKE_HS_STATE_FILE=/path/to/state.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

DEFAULT_LOCATIONS = """Virtual locations:
CODE  NAME
US    United States
USNY  United States - New York
DE    Germany
FR    France
GB    United Kingdom
JP    Japan
CA    Canada
AU    Australia
BR    Brazil
IN    India
SG    Singapore
NL    Netherlands
SE    Sweden
CH    Switzerland
IT    Italy
ES    Spain
KR    Korea
MX    Mexico
AE    United Arab Emirates
HK    Hong Kong
"""


def state_path() -> Path:
    raw = os.environ.get("FAKE_HS_STATE_FILE")
    if raw:
        return Path(raw)
    return Path(os.environ.get("TMPDIR", "/tmp")) / "fake_hotspotshield_state.json"


def load_state() -> dict:
    path = state_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "vpn": "disconnected",
        "location": None,
        "signed_in": False,
        "username": None,
    }


def save_state(state: dict) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def mode() -> str:
    return os.environ.get("FAKE_HS_MODE", "success").strip().lower()


def main(argv: list[str]) -> int:
    if mode() == "missing_executable":
        return 127
    if mode() == "permission_denied":
        print("Permission denied", file=sys.stderr)
        return 126
    if mode() == "timeout":
        time.sleep(float(os.environ.get("FAKE_HS_TIMEOUT_SLEEP", "30")))
        return 0
    if mode() == "network_failure":
        print("can't connect to HotspotShield servers. Please check your internet connection", file=sys.stderr)
        return 1

    if not argv:
        print("Usage: hotspotshield command [options]", file=sys.stderr)
        return 2

    cmd = argv[0]
    state = load_state()

    if cmd == "help":
        print(
            "Commands:\n"
            "  account [signin | status | signout]\n"
            "  connect VL\n"
            "  disconnect\n"
            "  locations\n"
            "  status\n"
            "  start\n"
            "  stop\n"
        )
        return 0

    if cmd == "start":
        print("started")
        return 0
    if cmd == "stop":
        state["vpn"] = "disconnected"
        state["location"] = None
        save_state(state)
        print("stopped")
        return 0

    if cmd == "status":
        loc = state.get("location")
        vpn = state.get("vpn", "disconnected")
        print(f"VPN connection state : {vpn}")
        if vpn == "connected" and loc:
            print(f"Connected location   : {loc}  ({loc})")
        return 0

    if cmd == "locations":
        if mode() == "empty_locations":
            print("Virtual locations:\nCODE  NAME\n")
            return 0
        if mode() == "malformed_output":
            print("<<<not a location table>>>")
            return 0
        if not state.get("signed_in"):
            print('You are not signed in. Please try via "hotspotshield account signin"', file=sys.stderr)
            return 1
        print(DEFAULT_LOCATIONS)
        return 0

    if cmd == "account":
        sub = argv[1] if len(argv) > 1 else "status"
        if sub == "signin":
            if mode() == "auth_failure":
                print("Invalid username or password", file=sys.stderr)
                return 1
            # Read credentials from stdin prompts
            sys.stdout.write("Username: ")
            sys.stdout.flush()
            username = sys.stdin.readline().strip()
            sys.stdout.write("Password: ")
            sys.stdout.flush()
            password = sys.stdin.readline().rstrip("\n")
            if not username or not password:
                print("Invalid username or password", file=sys.stderr)
                return 1
            state["signed_in"] = True
            state["username"] = username
            save_state(state)
            print("Signed in")
            return 0
        if sub == "signout":
            state["signed_in"] = False
            state["username"] = None
            save_state(state)
            print("Signed out")
            return 0
        # status
        if state.get("signed_in"):
            print(f"Signed in as {state.get('username')}")
            print("Account type: Premium")
            return 0
        print("You are not signed in.")
        return 0

    if cmd == "connect":
        if mode() == "slow_connect":
            time.sleep(float(os.environ.get("FAKE_HS_SLOW", "2")))
        if not state.get("signed_in"):
            print('You are not signed in. Please try via "hotspotshield account signin"', file=sys.stderr)
            return 1
        code = argv[1] if len(argv) > 1 else "US"
        if state.get("vpn") == "connected":
            print("VPN connection already established")
            print("  do 'hotspotshield status' to show current state")
            print("  do 'hotspotshield disconnect' first, if you want to change virtual location")
            return 1
        state["vpn"] = "connected"
        state["location"] = code
        save_state(state)
        print(f"Connected to {code}")
        return 0

    if cmd == "disconnect":
        if mode() == "disconnect_failure":
            print("Can't disconnect. Please check system journals for more info", file=sys.stderr)
            return 1
        if state.get("vpn") != "connected":
            print("hotspotshield in disconnected state already")
            state["vpn"] = "disconnected"
            state["location"] = None
            save_state(state)
            return 0
        state["vpn"] = "disconnected"
        state["location"] = None
        save_state(state)
        print("Disconnected")
        return 0

    print(f"unknown request command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
