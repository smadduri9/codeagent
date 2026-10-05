"""Shared provider contract checks (offline)."""

from collections.abc import Iterator

from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelEvent,
    ModelRequest,
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
from codeagent.providers.protocol import Provider
from codeagent.providers.stream import collect_stream


def run_contract_suite(provider: Provider) -> None:
    req = ModelRequest(
        system="system",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="test-model",
        max_output_tokens=64,
    )
    events = list(provider.stream(req))
    assert events
    assert any(isinstance(event, Stop) for event in events)
    assert provider.count_tokens([Message(role=MessageRole.USER, content="abcd")]) >= 1


def test_fake_provider_passes_contract() -> None:
    turn: list[ModelEvent] = [
        TextDelta(text="ok"),
        UsageEvent(usage=Usage(input=3, output=2)),
        Stop(reason=StopReason.STOP),
    ]
    run_contract_suite(FakeProvider([turn]))


def test_collect_stream_handles_tool_calls() -> None:
    events: Iterator[ModelEvent] = iter(
        [
            ToolCallStart(id="c1", name="echo"),
            ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "x"})),
            Stop(reason=StopReason.TOOL_CALLS),
        ],
    )
    reply = collect_stream(events)
    assert reply.tool_calls[0].name == "echo"
