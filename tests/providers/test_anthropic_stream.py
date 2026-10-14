"""Mapping from raw Anthropic SSE event dicts to codeagent model events."""

from codeagent.providers.anthropic_mapping import map_stream
from codeagent.providers.base import (
    Stop,
    StopReason,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallEnd,
    ToolCallStart,
    UsageEvent,
)


def test_text_only_stream() -> None:
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 12}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hi"}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 3},
        },
        {"type": "message_stop"},
    ]
    out = list(map_stream(events))
    assert [type(e) for e in out] == [TextDelta, UsageEvent, Stop]
    assert out[0] == TextDelta(text="Hi")
    assert out[1].usage.input == 12 and out[1].usage.output == 3
    assert out[2] == Stop(reason=StopReason.STOP)


def test_tool_call_args_split_across_deltas() -> None:
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "t1", "name": "read_file", "input": {}},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"pa'},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": 'th": "a'},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '.py"}'},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"output_tokens": 7},
        },
        {"type": "message_stop"},
    ]
    out = list(map_stream(events))
    assert isinstance(out[0], ToolCallStart) and out[0].id == "t1" and out[0].name == "read_file"
    deltas = [e.delta for e in out if isinstance(e, ToolCallArgsDelta)]
    assert "".join(deltas) == '{"path": "a.py"}'
    ends = [e for e in out if isinstance(e, ToolCallEnd)]
    assert ends[0].call.args == {"path": "a.py"}
    assert out[-1] == Stop(reason=StopReason.TOOL_CALLS)


def test_usage_carries_cache_fields() -> None:
    events = [
        {
            "type": "message_start",
            "message": {
                "usage": {
                    "input_tokens": 10,
                    "cache_read_input_tokens": 40,
                    "cache_creation_input_tokens": 5,
                },
            },
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "max_tokens"},
            "usage": {"output_tokens": 2},
        },
        {"type": "message_stop"},
    ]
    out = list(map_stream(events))
    usage = next(e for e in out if isinstance(e, UsageEvent)).usage
    assert (usage.input, usage.output, usage.cache_read, usage.cache_write) == (10, 2, 40, 5)
    assert out[-1] == Stop(reason=StopReason.LENGTH)
