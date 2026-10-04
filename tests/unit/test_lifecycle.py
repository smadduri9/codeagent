"""Lifecycle transition coverage."""

import logging

import pytest

from codeagent.lifecycle import (
    ALLOWED_TRANSITIONS,
    TERMINAL_PHASES,
    InvalidTransitionError,
    LifecycleState,
    RunPhase,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current, targets in ALLOWED_TRANSITIONS.items() for target in targets],
)
def test_allowed_transitions_succeed(
    current: RunPhase,
    target: RunPhase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = LifecycleState(phase=current)
    with caplog.at_level(logging.INFO):
        assert state.transition(target) == target
    assert any("run.phase_changed" in record.message for record in caplog.records)


def test_disallowed_transition_raises() -> None:
    state = LifecycleState(phase=RunPhase.COMPLETED)
    with pytest.raises(InvalidTransitionError):
        state.transition(RunPhase.WORKING)


def test_every_non_terminal_phase_has_outgoing_or_is_terminal() -> None:
    for phase in RunPhase:
        if phase in TERMINAL_PHASES:
            assert ALLOWED_TRANSITIONS[phase] == frozenset()
        else:
            assert ALLOWED_TRANSITIONS[phase]


def test_all_disallowed_pairs_raise() -> None:
    for current in RunPhase:
        allowed = ALLOWED_TRANSITIONS[current]
        for target in RunPhase:
            if target in allowed:
                continue
            state = LifecycleState(phase=current)
            with pytest.raises(InvalidTransitionError):
                state.transition(target)
