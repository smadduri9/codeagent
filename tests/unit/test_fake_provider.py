"""FakeProvider replays scripted turns without network access."""

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
    ToolCallArgsDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.providers.protocol import Provider


def _sample_request() -> ModelRequest:
    return ModelRequest(
        system="system",
        messages=[Message(role=MessageRole.USER, content="goal")],
        tools=[],
        model="test-model",
        max_output_tokens=128,
    )


def _collect(provider: Provider, req: ModelRequest) -> list[ModelEvent]:
    return list(provider.stream(req))


def test_three_turn_script_replays_exact_events() -> None:
    turn_one = [
        TextDelta(text="Let me "),
        TextDelta(text="look."),
        ToolCallStart(id="call_1", name="read_file"),
        ToolCallArgsDelta(id="call_1", delta='{"path":'),
        ToolCallArgsDelta(id="call_1", delta=' "README.md"}'),
        ToolCallEnd(call=ToolCall(id="call_1", name="read_file", args={"path": "README.md"})),
        UsageEvent(usage=Usage(input=40, output=12, cache_read=0, cache_write=0)),
        Stop(reason=StopReason.TOOL_CALLS),
    ]
    turn_two = [
        TextDelta(text="Found the answer."),
        UsageEvent(usage=Usage(input=80, output=6, cache_read=10, cache_write=0)),
        Stop(reason=StopReason.STOP),
    ]
    turn_three = [
        TextDelta(text="All set."),
        UsageEvent(usage=Usage(input=90, output=4)),
        Stop(reason=StopReason.STOP),
    ]
    script = [turn_one, turn_two, turn_three]
    provider: Provider = FakeProvider(script)

    for expected in script:
        assert _collect(provider, _sample_request()) == expected

    assert provider.turns_remaining == 0


def test_count_tokens_estimates_from_message_content() -> None:
    provider = FakeProvider([[]])
    messages = [
        Message(role=MessageRole.USER, content="abcd"),
        Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="c1", name="echo", args={"x": 1})],
        ),
    ]
    assert provider.count_tokens(messages) >= 1


def test_exhausted_script_yields_error_stop() -> None:
    provider = FakeProvider(
        [[TextDelta(text="once"), Stop(reason=StopReason.STOP)]],
    )
    req = _sample_request()
    assert list(provider.stream(req))[-1] == Stop(reason=StopReason.STOP)
    exhausted = list(provider.stream(req))
    assert exhausted[-1] == Stop(reason=StopReason.ERROR)


def test_stream_is_lazy() -> None:
    provider = FakeProvider([[TextDelta(text="a"), Stop(reason=StopReason.STOP)]])
    iterator: Iterator[ModelEvent] = provider.stream(_sample_request())
    assert next(iterator).kind == "text_delta"
