"""Budget guard stop reasons."""

from codeagent.config import LimitSettings, Price, Settings
from codeagent.loop.budget import BudgetTracker
from codeagent.loop.limits import RunLimits
from codeagent.loop.runner import run_agent_loop
from codeagent.providers.base import (
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.tools.registry import ToolRegistry


def _tool_turn() -> list[object]:
    return [
        ToolCallStart(id="c1", name="echo"),
        ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "x"})),
        UsageEvent(usage=Usage(input=10, output=10)),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


def _limits(**overrides: int | float) -> RunLimits:
    base = LimitSettings()
    data = base.model_dump()
    data.update(overrides)
    return RunLimits.from_settings(Settings(limits=LimitSettings(**data)), "m")


def test_budget_guard_max_total_tokens() -> None:
    limits = _limits(max_total_tokens=15)
    budget = BudgetTracker(limits=limits)
    registry = ToolRegistry()
    provider = FakeProvider([_tool_turn(), [TextDelta(text="done"), Stop(reason=StopReason.STOP)]])
    result = run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        limits=limits,
        budget=budget,
    )
    assert result.stop_reason == "max_total_tokens"
    assert result.exhaustion_report is not None


def test_budget_guard_max_tool_calls() -> None:
    limits = _limits(max_tool_calls=1)
    budget = BudgetTracker(limits=limits)
    registry = ToolRegistry()
    provider = FakeProvider([_tool_turn(), _tool_turn()])
    result = run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=10,
        limits=limits,
        budget=budget,
    )
    assert result.stop_reason == "max_tool_calls"


def test_budget_guard_max_cost_usd() -> None:
    limits = RunLimits.from_settings(
        Settings(
            limits=LimitSettings(max_cost_usd=0.000001),
            prices={"m": Price(input=1.0, output=1.0, cache_read=0.0)},
        ),
        "m",
    )
    budget = BudgetTracker(limits=limits)
    registry = ToolRegistry()
    provider = FakeProvider([_tool_turn()])
    result = run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        limits=limits,
        budget=budget,
        model="m",
    )
    assert result.stop_reason == "max_cost_usd"


def test_budget_guard_max_runtime_minutes() -> None:
    limits = _limits(max_runtime_minutes=1)
    budget = BudgetTracker(limits=limits)
    budget.started_monotonic -= 120.0
    registry = ToolRegistry()
    provider = FakeProvider([_tool_turn()])
    result = run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        limits=limits,
        budget=budget,
    )
    assert result.stop_reason == "max_runtime_minutes"
