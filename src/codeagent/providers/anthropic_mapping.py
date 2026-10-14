"""Pure mapping from codeagent model requests to the Anthropic Messages API shape.

No SDK import here, so the mapping is testable without the optional dependency.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

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


def _text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _assistant_content(message: Message) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if message.content:
        blocks.append(_text_block(message.content))
    for call in message.tool_calls:
        blocks.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.args},
        )
    return blocks


def _append_message(out: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
    """Append a message; consecutive tool results share one user message."""
    if role == "user" and out and out[-1]["role"] == "user" and _all_tool_results(blocks):
        if _all_tool_results(out[-1]["content"]):
            out[-1]["content"].extend(blocks)
            return
    out.append({"role": role, "content": blocks})


def _all_tool_results(blocks: list[dict[str, Any]]) -> bool:
    return bool(blocks) and all(block["type"] == "tool_result" for block in blocks)


def _convert_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role is MessageRole.TOOL:
            block = {
                "type": "tool_result",
                "tool_use_id": message.tool_call_id,
                "content": message.content or "",
            }
            _append_message(out, "user", [block])
        elif message.role is MessageRole.ASSISTANT:
            _append_message(out, "assistant", _assistant_content(message))
        else:
            _append_message(out, "user", [_text_block(message.content or "")])
    return out


def to_anthropic_request(req: ModelRequest) -> dict[str, Any]:
    """Build the keyword arguments for ``client.messages.create``."""
    return {
        "model": req.model,
        "max_tokens": req.max_output_tokens,
        "system": [
            {
                "type": "text",
                "text": req.system,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": _convert_messages(req.messages),
        "tools": [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.parameters,
            }
            for spec in req.tools
        ],
        "temperature": req.temperature,
    }


_STOP_REASONS = {
    "end_turn": StopReason.STOP,
    "stop_sequence": StopReason.STOP,
    "tool_use": StopReason.TOOL_CALLS,
    "max_tokens": StopReason.LENGTH,
}


def map_stream(events: Iterable[dict[str, Any]]) -> Iterator[ModelEvent]:
    """Map raw Anthropic SSE event dicts to codeagent model events."""
    input_tokens = cache_read = cache_write = 0
    output_tokens = 0
    tool_ids: dict[int, str] = {}
    tool_names: dict[int, str] = {}
    tool_args: dict[int, str] = {}
    stop_reason: StopReason | None = None
    for event in events:
        kind = event.get("type")
        if kind == "message_start":
            usage = event.get("message", {}).get("usage", {})
            input_tokens = int(usage.get("input_tokens", 0) or 0)
            cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
            cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
        elif kind == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                index = int(event.get("index", 0))
                tool_ids[index] = str(block.get("id"))
                tool_names[index] = str(block.get("name"))
                tool_args[index] = ""
                yield ToolCallStart(id=tool_ids[index], name=tool_names[index])
        elif kind == "content_block_delta":
            delta = event.get("delta", {})
            index = int(event.get("index", 0))
            if delta.get("type") == "text_delta":
                yield TextDelta(text=str(delta.get("text", "")))
            elif delta.get("type") == "input_json_delta" and index in tool_ids:
                partial = str(delta.get("partial_json", ""))
                tool_args[index] += partial
                yield ToolCallArgsDelta(id=tool_ids[index], delta=partial)
        elif kind == "content_block_stop":
            index = int(event.get("index", 0))
            if index in tool_ids:
                raw = tool_args.pop(index) or "{}"
                args = json.loads(raw)
                if not isinstance(args, dict):
                    args = {}
                yield ToolCallEnd(
                    call=ToolCall(id=tool_ids.pop(index), name=tool_names.pop(index), args=args),
                )
        elif kind == "message_delta":
            output_tokens = int(event.get("usage", {}).get("output_tokens", output_tokens) or 0)
            reason = event.get("delta", {}).get("stop_reason")
            stop_reason = _STOP_REASONS.get(str(reason), StopReason.STOP)
        elif kind == "message_stop":
            yield UsageEvent(
                usage=Usage(
                    input=input_tokens,
                    output=output_tokens,
                    cache_read=cache_read,
                    cache_write=cache_write,
                ),
            )
            yield Stop(reason=stop_reason or StopReason.STOP)
