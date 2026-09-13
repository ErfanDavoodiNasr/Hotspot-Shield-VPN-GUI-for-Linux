"""Explicit VPN connection state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class VpnState(str, Enum):
    INITIALIZING = "initializing"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    VERIFYING_CONNECTION = "verifying_connection"
    CONNECTED = "connected"
    SWITCHING_LOCATION = "switching_location"
    DISCONNECTING = "disconnecting"
    VERIFYING_DISCONNECTION = "verifying_disconnection"
    UNKNOWN = "unknown"
    ERROR = "error"


ALLOWED_TRANSITIONS: Final[dict[VpnState, frozenset[VpnState]]] = {
    VpnState.INITIALIZING: frozenset(
        {
            VpnState.DISCONNECTED,
            VpnState.VERIFYING_CONNECTION,
            VpnState.CONNECTED,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        }
    ),
    VpnState.DISCONNECTED: frozenset(
        {VpnState.CONNECTING, VpnState.INITIALIZING, VpnState.UNKNOWN, VpnState.ERROR}
    ),
    VpnState.CONNECTING: frozenset(
        {
            VpnState.VERIFYING_CONNECTION,
            VpnState.CONNECTED,
            VpnState.DISCONNECTED,
            VpnState.DISCONNECTING,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        }
    ),
    VpnState.VERIFYING_CONNECTION: frozenset(
        {
            VpnState.CONNECTED,
            VpnState.DISCONNECTED,
            VpnState.DISCONNECTING,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        }
    ),
    VpnState.CONNECTED: frozenset(
        {
            VpnState.SWITCHING_LOCATION,
            VpnState.DISCONNECTING,
            VpnState.UNKNOWN,
            VpnState.ERROR,
            VpnState.DISCONNECTED,
        }
    ),
    VpnState.SWITCHING_LOCATION: frozenset(
        {
            VpnState.VERIFYING_CONNECTION,
            VpnState.CONNECTED,
            VpnState.DISCONNECTED,
            VpnState.DISCONNECTING,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        }
    ),
    VpnState.DISCONNECTING: frozenset(
        {
            VpnState.VERIFYING_DISCONNECTION,
            VpnState.DISCONNECTED,
            VpnState.CONNECTED,
            VpnState.UNKNOWN,
            VpnState.ERROR,
        }
    ),
    VpnState.VERIFYING_DISCONNECTION: frozenset(
        {VpnState.DISCONNECTED, VpnState.CONNECTED, VpnState.UNKNOWN, VpnState.ERROR}
    ),
    VpnState.UNKNOWN: frozenset(
        {
            VpnState.DISCONNECTED,
            VpnState.CONNECTED,
            VpnState.CONNECTING,
            VpnState.DISCONNECTING,
            VpnState.INITIALIZING,
            VpnState.ERROR,
        }
    ),
    VpnState.ERROR: frozenset(
        {
            VpnState.DISCONNECTED,
            VpnState.CONNECTED,
            VpnState.CONNECTING,
            VpnState.DISCONNECTING,
            VpnState.INITIALIZING,
            VpnState.UNKNOWN,
        }
    ),
}


class InvalidTransitionError(ValueError):
    pass


@dataclass
class VpnStatusInfo:
    state: VpnState
    connected_location_code: str | None = None
    connected_location_name: str | None = None
    raw_state_token: str | None = None
    details: dict[str, str] = field(default_factory=dict)
    verified: bool = False

    @property
    def is_connected(self) -> bool:
        return self.state is VpnState.CONNECTED


@dataclass
class StateMachine:
    state: VpnState = VpnState.INITIALIZING
    last_error: str | None = None

    def can_transition(self, new_state: VpnState) -> bool:
        if new_state is self.state:
            return True
        return new_state in ALLOWED_TRANSITIONS[self.state]

    def transition(self, new_state: VpnState, *, error: str | None = None) -> VpnState:
        if new_state is self.state:
            if new_state is VpnState.ERROR and error is not None:
                self.last_error = error
            return self.state
        if not self.can_transition(new_state):
            raise InvalidTransitionError(
                f"Illegal transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state
        if new_state is VpnState.ERROR:
            self.last_error = error or self.last_error or "Unknown error"
        else:
            self.last_error = None
        return self.state

    def force(self, new_state: VpnState, *, error: str | None = None) -> VpnState:
        self.state = new_state
        self.last_error = error if new_state is VpnState.ERROR else None
        return self.state

    @property
    def busy(self) -> bool:
        return self.state in {
            VpnState.INITIALIZING,
            VpnState.CONNECTING,
            VpnState.VERIFYING_CONNECTION,
            VpnState.DISCONNECTING,
            VpnState.VERIFYING_DISCONNECTION,
            VpnState.SWITCHING_LOCATION,
        }

    @property
    def can_connect(self) -> bool:
        return self.state in {VpnState.DISCONNECTED, VpnState.ERROR, VpnState.UNKNOWN}

    @property
    def can_disconnect(self) -> bool:
        return self.state in {
            VpnState.CONNECTED,
            VpnState.ERROR,
            VpnState.UNKNOWN,
            VpnState.CONNECTING,
            VpnState.VERIFYING_CONNECTION,
            VpnState.SWITCHING_LOCATION,
        }

    @property
    def can_cancel(self) -> bool:
        return self.state in {
            VpnState.CONNECTING,
            VpnState.VERIFYING_CONNECTION,
            VpnState.SWITCHING_LOCATION,
        }

    @property
    def display_label(self) -> str:
        return {
            VpnState.INITIALIZING: "Checking status…",
            VpnState.DISCONNECTED: "Disconnected",
            VpnState.CONNECTING: "Connecting…",
            VpnState.VERIFYING_CONNECTION: "Verifying connection…",
            VpnState.CONNECTED: "Connected",
            VpnState.SWITCHING_LOCATION: "Changing location…",
            VpnState.DISCONNECTING: "Disconnecting…",
            VpnState.VERIFYING_DISCONNECTION: "Verifying disconnection…",
            VpnState.UNKNOWN: "Connection state unknown",
            VpnState.ERROR: "Error",
        }[self.state]
