"""Token estimation helpers (approximate, offline-safe)."""

from __future__ import annotations

from json import dumps

from codeagent.providers.base import Message
from codeagent.tools.base import ToolSpec


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_tool_specs_tokens(tools: list[ToolSpec]) -> int:
    payload = [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in tools
    ]
    return estimate_text_tokens(dumps(payload, sort_keys=True))


def estimate_messages_tokens(messages: list[Message]) -> int:
    total = 0
    for message in messages:
        if message.content:
            total += estimate_text_tokens(message.content)
        for call in message.tool_calls:
            total += estimate_text_tokens(
                call.id + call.name + dumps(call.args, sort_keys=True),
            )
    return total
