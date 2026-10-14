"""Pure mapping from codeagent model requests to the Anthropic Messages API shape.

No SDK import here, so the mapping is testable without the optional dependency.
"""

from __future__ import annotations

from typing import Any

from codeagent.providers.base import Message, MessageRole, ModelRequest


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
