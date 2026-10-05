"""Collect streaming provider events into a single model reply."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from json import loads

from codeagent.providers.base import (
    ModelEvent,
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


@dataclass
class ModelReply:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None
    stop_reason: StopReason | None = None


def collect_stream(
    events: Iterator[ModelEvent],
    *,
    on_text_delta: Callable[[str], None] | None = None,
    on_tool_announced: Callable[[str], None] | None = None,
) -> ModelReply:
    reply = ModelReply()
    pending_args: dict[str, str] = {}
    pending_names: dict[str, str] = {}
    for event in events:
        if isinstance(event, TextDelta):
            reply.content += event.text
            if on_text_delta is not None and event.text:
                on_text_delta(event.text)
        elif isinstance(event, ToolCallStart):
            pending_names[event.id] = event.name
            pending_args.setdefault(event.id, "")
            if on_tool_announced is not None:
                on_tool_announced(event.name)
        elif isinstance(event, ToolCallArgsDelta):
            pending_args[event.id] = pending_args.get(event.id, "") + event.delta
        elif isinstance(event, ToolCallEnd):
            reply.tool_calls.append(event.call)
            pending_args.pop(event.call.id, None)
            pending_names.pop(event.call.id, None)
        elif isinstance(event, UsageEvent):
            reply.usage = event.usage
        elif isinstance(event, Stop):
            reply.stop_reason = event.reason
    for call_id, name in list(pending_names.items()):
        raw = pending_args.get(call_id, "")
        args: dict[str, object] = {}
        if raw:
            parsed = loads(raw)
            if isinstance(parsed, dict):
                args = parsed
        reply.tool_calls.append(ToolCall(id=call_id, name=name, args=args))
    return reply
