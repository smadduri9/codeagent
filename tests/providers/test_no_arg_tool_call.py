"""A streamed tool call that carries no argument text is still a tool call."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from openai.types.chat import ChatCompletionChunk

from codeagent.providers.base import Message, MessageRole, ModelRequest, Stop, ToolCallEnd
from codeagent.providers.openai_compatible import OpenAICompatibleProvider


def _chunk(delta: dict[str, Any], finish: str | None = None) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate(
        {
            "id": "x",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
    )


def _tool(index: int, call_id: str, name: str, arguments: str | None) -> dict[str, Any]:
    function: dict[str, Any] = {"name": name}
    if arguments is not None:
        function["arguments"] = arguments
    return {"index": index, "id": call_id, "type": "function", "function": function}


def _calls(chunks: list[ChatCompletionChunk]) -> list[tuple[str, str, dict[str, object]]]:
    def factory(**_kwargs: Any) -> Iterator[ChatCompletionChunk]:
        yield from chunks

    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:1", api_key_env="CODEAGENT_TEST_UNSET", stream_factory=factory
    )
    request = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    events = list(provider.stream(request))
    assert isinstance(events[-1], Stop)
    return [(e.call.id, e.call.name, e.call.args) for e in events if isinstance(e, ToolCallEnd)]


@pytest.mark.parametrize("arguments", [None, ""], ids=["missing", "empty"])
def test_tool_call_without_argument_text_is_emitted(arguments: str | None) -> None:
    chunks = [
        _chunk({"tool_calls": [_tool(0, "c1", "git_status", arguments)]}),
        _chunk({}, finish="tool_calls"),
    ]
    assert _calls(chunks) == [("c1", "git_status", {})]


def test_no_arg_call_is_kept_next_to_a_call_with_arguments() -> None:
    chunks = [
        _chunk({"tool_calls": [_tool(0, "c1", "git_status", None)]}),
        _chunk({"tool_calls": [_tool(1, "c2", "read_file", '{"path": "a.py"}')]}),
        _chunk({}, finish="tool_calls"),
    ]
    assert _calls(chunks) == [("c1", "git_status", {}), ("c2", "read_file", {"path": "a.py"})]


def test_call_with_arguments_is_unchanged() -> None:
    chunks = [
        _chunk({"tool_calls": [_tool(0, "c1", "read_file", '{"path": ')]}),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"a.py"}'}}]}),
        _chunk({}, finish="tool_calls"),
    ]
    assert _calls(chunks) == [("c1", "read_file", {"path": "a.py"})]
