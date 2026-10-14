"""FaultyProvider injects each fault kind on the chosen call index."""

import pytest

from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelRequest,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallArgsDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.providers.faulty import Fault, FaultyProvider
from codeagent.providers.quota_errors import ProviderError, RateLimitError


def _req() -> ModelRequest:
    return ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=10,
    )


def _text_turn() -> list[object]:
    return [
        TextDelta(text="ok"),
        UsageEvent(usage=Usage(input=1, output=1)),
        Stop(reason=StopReason.STOP),
    ]


def _tool_turn() -> list[object]:
    return [
        ToolCallStart(id="c1", name="read_file"),
        ToolCallArgsDelta(id="c1", delta='{"path": "a.py"}'),
        ToolCallEnd(call=ToolCall(id="c1", name="read_file", args={"path": "a.py"})),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


def test_rate_limit_raises_on_chosen_call_then_passes_through() -> None:
    inner = FakeProvider([_text_turn(), _text_turn()])
    provider = FaultyProvider(inner, [Fault(kind="rate_limit", on_call=0)])
    with pytest.raises(RateLimitError):
        list(provider.stream(_req()))
    events = list(provider.stream(_req()))
    assert any(isinstance(e, TextDelta) for e in events)


def test_server_error_raises_provider_error() -> None:
    provider = FaultyProvider(FakeProvider([_text_turn()]), [Fault(kind="server_error", on_call=0)])
    with pytest.raises(ProviderError, match="500"):
        list(provider.stream(_req()))


def test_timeout_raises_provider_error() -> None:
    provider = FaultyProvider(FakeProvider([_text_turn()]), [Fault(kind="timeout", on_call=0)])
    with pytest.raises(ProviderError, match="timeout"):
        list(provider.stream(_req()))


def test_truncate_stops_after_first_args_delta() -> None:
    provider = FaultyProvider(FakeProvider([_tool_turn()]), [Fault(kind="truncate", on_call=0)])
    events = list(provider.stream(_req()))
    assert any(isinstance(e, ToolCallArgsDelta) for e in events)
    assert not any(isinstance(e, ToolCallEnd) for e in events)
    assert not any(isinstance(e, Stop) for e in events)


def test_bad_tool_json_corrupts_first_tool_call_args() -> None:
    provider = FaultyProvider(
        FakeProvider([_tool_turn()]),
        [Fault(kind="bad_tool_json", on_call=0)],
    )
    events = list(provider.stream(_req()))
    deltas = [e.delta for e in events if isinstance(e, ToolCallArgsDelta)]
    assert deltas[-1] == '{"path": '
    assert not any(isinstance(e, ToolCallEnd) for e in events)


def test_unfaulted_calls_pass_through_unchanged() -> None:
    provider = FaultyProvider(FakeProvider([_text_turn()]), [])
    assert [type(e) for e in provider.stream(_req())] == [type(e) for e in _text_turn()]
