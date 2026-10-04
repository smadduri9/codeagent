"""Loop guards for iterations, repeats, and denials."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from codeagent.providers.base import ToolCall


class GuardStopReason(StrEnum):
    MAX_ITERATIONS = "max_iterations"
    REPEAT_TOOL_CALLS = "repeat_tool_calls"
    DENIAL_STREAK = "denial_streak"


@dataclass(frozen=True)
class GuardResult:
    stop: bool
    reason: GuardStopReason | None = None
    warning: str | None = None


@dataclass
class LoopGuardState:
    max_iterations: int
    iterations: int = 0
    repeat_warned: bool = False
    recent_calls: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=6))
    denial_streak: int = 0


class LoopGuards:
    """Iteration limit, repeat detection, and denial streak tracking."""

    def __init__(self, max_iterations: int) -> None:
        self.state = LoopGuardState(max_iterations=max_iterations)

    def on_iteration_start(self) -> GuardResult:
        if self.state.iterations >= self.state.max_iterations:
            return GuardResult(stop=True, reason=GuardStopReason.MAX_ITERATIONS)
        self.state.iterations += 1
        return GuardResult(stop=False)

    def on_tool_call(self, call: ToolCall) -> GuardResult:
        signature = (call.name, _args_signature(call.args))
        self.state.recent_calls.append(signature)
        if _count_identical(self.state.recent_calls, signature) >= 3:
            if not self.state.repeat_warned:
                self.state.repeat_warned = True
                return GuardResult(
                    stop=False,
                    warning="repeated identical tool call detected",
                )
            return GuardResult(stop=True, reason=GuardStopReason.REPEAT_TOOL_CALLS)
        return GuardResult(stop=False)

    def on_denial(self) -> GuardResult:
        self.state.denial_streak += 1
        if self.state.denial_streak >= 3:
            return GuardResult(stop=True, reason=GuardStopReason.DENIAL_STREAK)
        return GuardResult(stop=False)

    def on_allow(self) -> None:
        self.state.denial_streak = 0


def _args_signature(args: dict[str, object]) -> str:
    return repr(sorted(args.items()))


def _count_identical(recent: deque[tuple[str, str]], target: tuple[str, str]) -> int:
    return sum(1 for item in recent if item == target)
