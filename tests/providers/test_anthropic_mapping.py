"""Mapping from codeagent requests to the Anthropic Messages API shape."""

from codeagent.providers.anthropic_mapping import to_anthropic_request
from codeagent.providers.base import Message, MessageRole, ModelRequest, ToolCall
from codeagent.tools.base import ToolSpec


def _request(messages: list[Message]) -> ModelRequest:
    return ModelRequest(
        system="sys",
        messages=messages,
        tools=[
            ToolSpec(
                name="read_file",
                description="Read a file.",
                parameters={"type": "object", "properties": {}},
            ),
        ],
        model="claude-test",
        max_output_tokens=100,
    )


def test_system_is_cached_and_model_and_limits_are_copied() -> None:
    body = to_anthropic_request(_request([Message(role=MessageRole.USER, content="hi")]))
    assert body["model"] == "claude-test"
    assert body["max_tokens"] == 100
    assert body["system"] == [
        {"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}},
    ]


def test_user_and_assistant_text_map_to_text_blocks() -> None:
    body = to_anthropic_request(
        _request(
            [
                Message(role=MessageRole.USER, content="hi"),
                Message(role=MessageRole.ASSISTANT, content="hello"),
            ],
        ),
    )
    assert body["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
    ]


def test_assistant_tool_call_maps_to_tool_use_block() -> None:
    call = ToolCall(id="t1", name="read_file", args={"path": "a.py"})
    body = to_anthropic_request(
        _request([Message(role=MessageRole.ASSISTANT, content=None, tool_calls=[call])]),
    )
    assert body["messages"] == [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a.py"}},
            ],
        },
    ]


def test_consecutive_tool_results_merge_into_one_user_message() -> None:
    body = to_anthropic_request(
        _request(
            [
                Message(role=MessageRole.TOOL, content="one", tool_call_id="t1"),
                Message(role=MessageRole.TOOL, content="two", tool_call_id="t2"),
            ],
        ),
    )
    assert body["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "one"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "two"},
            ],
        },
    ]


def test_tools_map_to_input_schema() -> None:
    body = to_anthropic_request(_request([Message(role=MessageRole.USER, content="hi")]))
    assert body["tools"] == [
        {
            "name": "read_file",
            "description": "Read a file.",
            "input_schema": {"type": "object", "properties": {}},
        },
    ]
