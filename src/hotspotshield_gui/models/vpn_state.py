"""Explicit VPN connection state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class VpnState(str, Enum):
    INITIALIZING = "initializing"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SWITCHING_LOCATION = "switching_location"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


ALLOWED_TRANSITIONS: Final[dict[VpnState, frozenset[VpnState]]] = {
    VpnState.INITIALIZING: frozenset({VpnState.DISCONNECTED, VpnState.CONNECTED, VpnState.ERROR}),
    VpnState.DISCONNECTED: frozenset({VpnState.CONNECTING, VpnState.INITIALIZING, VpnState.ERROR}),
    # Cancel connect → DISCONNECTING or DISCONNECTED
    VpnState.CONNECTING: frozenset(
        {VpnState.CONNECTED, VpnState.DISCONNECTED, VpnState.DISCONNECTING, VpnState.ERROR}
    ),
    VpnState.CONNECTED: frozenset(
        {VpnState.SWITCHING_LOCATION, VpnState.DISCONNECTING, VpnState.ERROR, VpnState.DISCONNECTED}
    ),
    # Cancel switch → DISCONNECTING
    VpnState.SWITCHING_LOCATION: frozenset(
        {VpnState.CONNECTED, VpnState.DISCONNECTED, VpnState.DISCONNECTING, VpnState.ERROR}
    ),
    VpnState.DISCONNECTING: frozenset({VpnState.DISCONNECTED, VpnState.ERROR, VpnState.CONNECTED}),
    VpnState.ERROR: frozenset(
        {
            VpnState.DISCONNECTED,
            VpnState.CONNECTED,
            VpnState.CONNECTING,
            VpnState.DISCONNECTING,
            VpnState.INITIALIZING,
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
            VpnState.DISCONNECTING,
            VpnState.SWITCHING_LOCATION,
        }

    @property
    def can_connect(self) -> bool:
        return self.state in {VpnState.DISCONNECTED, VpnState.ERROR}

    @property
    def can_disconnect(self) -> bool:
        return self.state in {
            VpnState.CONNECTED,
            VpnState.ERROR,
            VpnState.CONNECTING,
            VpnState.SWITCHING_LOCATION,
        }

    @property
    def can_cancel(self) -> bool:
        return self.state in {VpnState.CONNECTING, VpnState.SWITCHING_LOCATION}

    @property
    def display_label(self) -> str:
        return {
            VpnState.INITIALIZING: "Checking status…",
            VpnState.DISCONNECTED: "Disconnected",
            VpnState.CONNECTING: "Connecting…",
            VpnState.CONNECTED: "Connected",
            VpnState.SWITCHING_LOCATION: "Changing location…",
            VpnState.DISCONNECTING: "Disconnecting…",
            VpnState.ERROR: "Error",
        }[self.state]
