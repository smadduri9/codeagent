"""Run lifecycle phases and validated transitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class RunPhase(StrEnum):
    INITIALIZING = "initializing"
    WORKING = "working"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_QUOTA = "waiting_quota"
    VERIFYING = "verifying"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    COMPLETED_UNVERIFIED = "completed_unverified"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_PHASES = frozenset(
    {
        RunPhase.COMPLETED,
        RunPhase.COMPLETED_UNVERIFIED,
        RunPhase.STOPPED,
        RunPhase.FAILED,
        RunPhase.CANCELLED,
    }
)

ALLOWED_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.INITIALIZING: frozenset(
        {RunPhase.WORKING, RunPhase.FAILED, RunPhase.CANCELLED},
    ),
    RunPhase.WORKING: frozenset(
        {
            RunPhase.WAITING_APPROVAL,
            RunPhase.WAITING_QUOTA,
            RunPhase.VERIFYING,
            RunPhase.REPLANNING,
            RunPhase.COMPLETED,
            RunPhase.COMPLETED_UNVERIFIED,
            RunPhase.STOPPED,
            RunPhase.FAILED,
            RunPhase.CANCELLED,
        },
    ),
    RunPhase.WAITING_APPROVAL: frozenset(
        {RunPhase.WORKING, RunPhase.STOPPED, RunPhase.FAILED, RunPhase.CANCELLED},
    ),
    RunPhase.WAITING_QUOTA: frozenset(
        {RunPhase.WORKING, RunPhase.STOPPED, RunPhase.CANCELLED},
    ),
    RunPhase.VERIFYING: frozenset(
        {
            RunPhase.COMPLETED,
            RunPhase.COMPLETED_UNVERIFIED,
            RunPhase.REPLANNING,
            RunPhase.WORKING,
            RunPhase.FAILED,
            RunPhase.STOPPED,
        },
    ),
    RunPhase.REPLANNING: frozenset(
        {RunPhase.WORKING, RunPhase.FAILED, RunPhase.CANCELLED, RunPhase.STOPPED},
    ),
    RunPhase.COMPLETED: frozenset(),
    RunPhase.COMPLETED_UNVERIFIED: frozenset(),
    RunPhase.STOPPED: frozenset(),
    RunPhase.FAILED: frozenset(),
    RunPhase.CANCELLED: frozenset(),
}


class InvalidTransitionError(ValueError):
    """Disallowed lifecycle transition."""

    def __init__(self, current: RunPhase, target: RunPhase) -> None:
        super().__init__(f"invalid transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


@dataclass
class LifecycleState:
    phase: RunPhase = RunPhase.INITIALIZING
    history: list[tuple[RunPhase, RunPhase]] = field(default_factory=list)

    def transition(self, target: RunPhase) -> RunPhase:
        allowed = ALLOWED_TRANSITIONS[self.phase]
        if target not in allowed:
            raise InvalidTransitionError(self.phase, target)
        previous = self.phase
        self.phase = target
        self.history.append((previous, target))
        logger.info(
            "run.phase_changed",
            extra={"from": previous.value, "to": target.value},
        )
        return self.phase
