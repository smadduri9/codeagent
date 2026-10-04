"""Agent loop and guard tests."""

from codeagent.loop import PermissionDecision, run_agent_loop
from codeagent.loop.guards import LoopGuards
from codeagent.providers.base import (
    MessageRole,
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


def test_loop_completes_after_one_tool_call() -> None:
    registry = ToolRegistry()
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="echo"),
                ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "ok"})),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.TOOL_CALLS),
            ],
            [
                TextDelta(text="done"),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.STOP),
            ],
        ],
    )
    result = run_agent_loop("hello", provider, registry, max_iterations=5)
    assert result.stop_reason == StopReason.STOP.value
    assert any(message.role is MessageRole.TOOL for message in result.history)


def test_loop_stops_at_max_iterations() -> None:
    registry = ToolRegistry()
    repeating = [
        TextDelta(text="again"),
        ToolCallStart(id="c1", name="echo"),
        ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "x"})),
        Stop(reason=StopReason.TOOL_CALLS),
    ]
    provider = FakeProvider([repeating, repeating, repeating, repeating])
    result = run_agent_loop("loop", provider, registry, max_iterations=3)
    assert result.stop_reason == "max_iterations"
    assert result.iterations == 3


def test_text_only_reply_ends_run() -> None:
    registry = ToolRegistry()
    provider = FakeProvider(
        [[TextDelta(text="finished"), Stop(reason=StopReason.STOP)]],
    )
    result = run_agent_loop("done", provider, registry, max_iterations=3)
    assert result.stop_reason == StopReason.STOP.value


def test_repeat_guard_warns_then_stops() -> None:
    registry = ToolRegistry()
    call = ToolCall(id="c1", name="echo", args={"message": "same"})
    turn = [
        ToolCallStart(id="c1", name="echo"),
        ToolCallEnd(call=call),
        Stop(reason=StopReason.TOOL_CALLS),
    ]
    provider = FakeProvider([turn, turn, turn, turn, turn, turn, turn])
    result = run_agent_loop("repeat", provider, registry, max_iterations=20)
    assert result.guard_warning is not None
    assert result.stop_reason == "repeat_tool_calls"


def test_denial_streak_stops_run() -> None:
    registry = ToolRegistry()
    turn = [
        ToolCallStart(id="c1", name="echo"),
        ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "x"})),
        Stop(reason=StopReason.TOOL_CALLS),
    ]
    provider = FakeProvider([turn, turn, turn, turn])
    result = run_agent_loop(
        "deny",
        provider,
        registry,
        max_iterations=10,
        decide=lambda _call: PermissionDecision.DENY,
    )
    assert result.stop_reason == "denial_streak"


def test_guard_iteration_limit() -> None:
    guards = LoopGuards(max_iterations=2)
    assert guards.on_iteration_start().stop is False
    assert guards.on_iteration_start().stop is False
    assert guards.on_iteration_start().stop is True
