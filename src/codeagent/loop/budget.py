"""Token, cost, tool-call, and runtime budget guards."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from codeagent.loop.limits import RunLimits
from codeagent.providers.base import Usage


class BudgetStopReason(StrEnum):
    MAX_TOTAL_TOKENS = "max_total_tokens"
    MAX_COST_USD = "max_cost_usd"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_RUNTIME_MINUTES = "max_runtime_minutes"


@dataclass(frozen=True)
class BudgetGuardResult:
    stop: bool
    reason: BudgetStopReason | None = None


@dataclass
class BudgetTracker:
    limits: RunLimits
    started_monotonic: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    def add_usage(self, usage: Usage) -> None:
        self.tokens_in += usage.input
        self.tokens_out += usage.output
        price = self.limits.prices.get(self.limits.model)
        if price is not None:
            self.cost_usd += (
                usage.input * price.input
                + usage.output * price.output
                + usage.cache_read * price.cache_read
            ) / 1_000_000

    def on_tool_completed(self) -> None:
        self.tool_calls += 1

    def check(self) -> BudgetGuardResult:
        total_tokens = self.tokens_in + self.tokens_out
        if total_tokens >= self.limits.max_total_tokens:
            return BudgetGuardResult(stop=True, reason=BudgetStopReason.MAX_TOTAL_TOKENS)
        if self.limits.cost_guard_enabled() and self.cost_usd >= self.limits.max_cost_usd:
            return BudgetGuardResult(stop=True, reason=BudgetStopReason.MAX_COST_USD)
        if self.tool_calls >= self.limits.max_tool_calls:
            return BudgetGuardResult(stop=True, reason=BudgetStopReason.MAX_TOOL_CALLS)
        elapsed_minutes = (time.monotonic() - self.started_monotonic) / 60.0
        if elapsed_minutes >= self.limits.max_runtime_minutes:
            return BudgetGuardResult(stop=True, reason=BudgetStopReason.MAX_RUNTIME_MINUTES)
        return BudgetGuardResult(stop=False)


@dataclass(frozen=True, slots=True)
class ExhaustionReport:
    work_accomplished: str
    current_failure: str | None
    changed_files: list[str]
    verification_state: str
    suggested_continuation: str


def build_exhaustion_report(
    *,
    goal: str,
    stop_reason: str,
    iterations: int,
    tool_calls: int,
    changed_files: list[str] | None = None,
) -> ExhaustionReport:
    changed = changed_files or []
    return ExhaustionReport(
        work_accomplished=(
            f"Completed {iterations} model turn(s) and {tool_calls} tool call(s) toward: {goal}"
        ),
        current_failure=stop_reason if stop_reason != "stop" else None,
        changed_files=changed,
        verification_state="not_run",
        suggested_continuation=(
            "Resume with `codeagent resume <run_id>` after adjusting limits or goal."
        ),
    )
