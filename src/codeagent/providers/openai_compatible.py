"""OpenAI-compatible streaming provider (Groq and similar endpoints)."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from json import dumps, loads
from typing import Any, Protocol

from openai import OpenAI
from openai.types.chat import ChatCompletionChunk

from codeagent.context.tokens import estimate_messages_tokens
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
from codeagent.providers.quota_errors import ContextOverflowError


class StreamClient(Protocol):
    def create(self, **kwargs: Any) -> Iterator[ChatCompletionChunk]:
        """Stream chat completion chunks."""


class OpenAICompatibleProvider:
    """Chat Completions with streaming and normalized tool calls."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key_env: str,
        client: OpenAI | None = None,
        stream_factory: Callable[..., Iterator[ChatCompletionChunk]] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self._stream_factory = stream_factory
        if client is not None:
            self._client = client
        else:
            resolved = os.environ.get(api_key_env, "")
            self._client = OpenAI(base_url=self.base_url, api_key=resolved or "missing")

    def list_models(self) -> list[str]:
        models = self._client.models.list()
        return [item.id for item in models.data]

    def count_tokens(self, messages: list[Message]) -> int:
        return estimate_messages_tokens(messages)

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        try:
            chunks = self._iter_chunks(req)
            yield from self._normalize_stream(chunks)
        except ContextOverflowError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped for callers
            message = str(exc).lower()
            if "too large" in message or "context" in message and "length" in message:
                raise ContextOverflowError(str(exc)) from exc
            raise

    def _iter_chunks(self, req: ModelRequest) -> Iterator[ChatCompletionChunk]:
        payload = self._build_payload(req)
        if self._stream_factory is not None:
            yield from self._stream_factory(**payload)
            return
        stream = self._client.chat.completions.create(**payload)
        yield from stream

    def _build_payload(self, req: ModelRequest) -> dict[str, Any]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in req.tools
        ]
        messages: list[dict[str, Any]] = [{"role": "system", "content": req.system}]
        for message in req.messages:
            messages.append(_message_to_api(message))
        payload: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "max_tokens": req.max_output_tokens,
            "temperature": req.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
        return payload

    def _normalize_stream(
        self,
        chunks: Iterator[ChatCompletionChunk],
    ) -> Iterator[ModelEvent]:
        pending_args: dict[int, str] = {}
        pending_names: dict[int, str] = {}
        pending_ids: dict[int, str] = {}
        for chunk in chunks:
            if chunk.usage is not None:
                detail = getattr(chunk.usage, "prompt_tokens_details", None)
                cache_read = 0
                if detail is not None:
                    cache_read = int(getattr(detail, "cached_tokens", 0) or 0)
                yield UsageEvent(
                    usage=Usage(
                        input=int(chunk.usage.prompt_tokens or 0),
                        output=int(chunk.usage.completion_tokens or 0),
                        cache_read=cache_read,
                    ),
                )
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = choice.delta
            if delta.content:
                yield TextDelta(text=delta.content)
            if delta.tool_calls:
                for tool_delta in delta.tool_calls:
                    index = int(tool_delta.index or 0)
                    if tool_delta.id:
                        pending_ids[index] = tool_delta.id
                    if tool_delta.function and tool_delta.function.name:
                        pending_names[index] = tool_delta.function.name
                        yield ToolCallStart(
                            id=pending_ids[index],
                            name=tool_delta.function.name,
                        )
                    if tool_delta.function and tool_delta.function.arguments:
                        pending_args[index] = (
                            pending_args.get(index, "") + tool_delta.function.arguments
                        )
                        yield ToolCallArgsDelta(
                            id=pending_ids[index],
                            delta=tool_delta.function.arguments,
                        )
            if choice.finish_reason:
                for index, raw_args in pending_args.items():
                    call_id = pending_ids.get(index, f"call_{index}")
                    name = pending_names.get(index, "unknown")
                    args = _parse_tool_args(raw_args)
                    yield ToolCallEnd(call=ToolCall(id=call_id, name=name, args=args))
                pending_args.clear()
                pending_ids.clear()
                pending_names.clear()
                reason = _map_finish_reason(choice.finish_reason)
                yield Stop(reason=reason)


def _parse_tool_args(raw: str) -> dict[str, object]:
    if not raw.strip():
        return {}
    try:
        parsed = loads(raw)
    except ValueError:
        return {"__invalid_json__": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"__invalid_json__": raw}


def _map_finish_reason(reason: str) -> StopReason:
    mapping = {
        "stop": StopReason.STOP,
        "length": StopReason.LENGTH,
        "tool_calls": StopReason.TOOL_CALLS,
        "content_filter": StopReason.CONTENT_FILTER,
    }
    return mapping.get(reason, StopReason.ERROR)


def _message_to_api(message: Message) -> dict[str, Any]:
    if message.role is MessageRole.TOOL:
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content or "",
        }
    if message.role is MessageRole.ASSISTANT:
        payload: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": dumps(call.args),
                    },
                }
                for call in message.tool_calls
            ]
        return payload
    return {"role": "user", "content": message.content or ""}
