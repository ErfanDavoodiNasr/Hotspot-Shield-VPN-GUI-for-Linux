"""State machine unit tests."""

from __future__ import annotations

import pytest

from hotspotshield_gui.models.vpn_state import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    StateMachine,
    VpnState,
)


@pytest.mark.parametrize(
    ("start", "end"),
    [(start, end) for start, ends in ALLOWED_TRANSITIONS.items() for end in ends],
)
def test_allowed_transitions(start: VpnState, end: VpnState) -> None:
    sm = StateMachine(state=start)
    assert sm.can_transition(end)
    sm.transition(end)
    assert sm.state is end


def test_illegal_transition_rejected() -> None:
    sm = StateMachine(state=VpnState.DISCONNECTED)
    with pytest.raises(InvalidTransitionError):
        sm.transition(VpnState.DISCONNECTING)


def test_idempotent_same_state() -> None:
    sm = StateMachine(state=VpnState.CONNECTED)
    assert sm.transition(VpnState.CONNECTED) is VpnState.CONNECTED


def test_force_reconcile() -> None:
    sm = StateMachine(state=VpnState.CONNECTING)
    sm.force(VpnState.CONNECTED)
    assert sm.state is VpnState.CONNECTED
    assert sm.last_error is None


def test_busy_flags() -> None:
    assert StateMachine(state=VpnState.CONNECTING).busy
    assert not StateMachine(state=VpnState.CONNECTED).busy
    assert StateMachine(state=VpnState.DISCONNECTED).can_connect
    assert StateMachine(state=VpnState.CONNECTED).can_disconnect


def test_error_clears_on_success() -> None:
    sm = StateMachine(state=VpnState.ERROR, last_error="boom")
    sm.transition(VpnState.DISCONNECTED)
    assert sm.last_error is None
