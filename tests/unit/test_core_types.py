"""Round-trip serialization for core provider and tool types."""

import pytest
from pydantic import TypeAdapter, ValidationError

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
from codeagent.tools.base import ToolResult, ToolSpec


def test_message_with_tool_calls_round_trip() -> None:
    message = Message(
        role=MessageRole.ASSISTANT,
        content="Checking the file.",
        tool_calls=[
            ToolCall(id="call_1", name="read_file", args={"path": "src/main.py", "limit": 10}),
        ],
    )
    restored = Message.model_validate_json(message.model_dump_json())
    assert restored == message


def test_tool_message_round_trip() -> None:
    message = Message(
        role=MessageRole.TOOL,
        content='{"lines": 3}',
        tool_call_id="call_1",
        name="read_file",
    )
    payload_json = message.model_dump_json()
    assert Message.model_validate_json(payload_json) == message


@pytest.mark.parametrize(
    "event",
    [
        TextDelta(text="hello"),
        ToolCallStart(id="c1", name="grep"),
        ToolCallArgsDelta(id="c1", delta='{"pattern":'),
        ToolCallEnd(call=ToolCall(id="c1", name="grep", args={"pattern": "TODO"})),
        UsageEvent(usage=Usage(input=12, output=4, cache_read=1, cache_write=0)),
        Stop(reason=StopReason.STOP),
    ],
)
def test_model_event_round_trip(event: ModelEvent) -> None:
    adapter = TypeAdapter(ModelEvent)
    payload = adapter.dump_json(event).decode()
    restored = adapter.validate_json(payload)
    assert restored == event


def test_model_request_round_trip() -> None:
    request = ModelRequest(
        system="You are a coding agent.",
        messages=[Message(role=MessageRole.USER, content="Fix the bug.")],
        tools=[
            ToolSpec(
                name="read_file",
                description="Read a file from the workspace.",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
        ],
        model="configured-model",
        max_output_tokens=512,
        temperature=0.2,
    )
    restored = ModelRequest.model_validate_json(request.model_dump_json())
    assert restored == request


def test_tool_result_round_trip() -> None:
    result = ToolResult(
        ok=True,
        summary="read 3 lines",
        content="1|alpha\n2|beta\n",
        truncated=False,
        exit_code=0,
        duration_ms=15,
    )
    restored = ToolResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_model_event_rejects_unknown_kind() -> None:
    adapter = TypeAdapter(ModelEvent)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "unknown", "text": "nope"})
