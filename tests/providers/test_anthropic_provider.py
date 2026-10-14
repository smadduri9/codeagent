"""AnthropicProvider passes the shared contract checks with a fake SDK client."""

from typing import Any

import pytest

from codeagent.providers.anthropic import AnthropicProvider
from codeagent.providers.base import Message, MessageRole, ModelRequest
from codeagent.providers.quota_errors import ProviderError
from tests.providers.test_contract import run_contract_suite


class _Event:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return self._data


class _Messages:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> list[_Event]:
        self.calls.append(kwargs)
        return [_Event(e) for e in self._events]


class _Client:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.messages = _Messages(events)


_TEXT_EVENTS: list[dict[str, Any]] = [
    {"type": "message_start", "message": {"usage": {"input_tokens": 3}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "ok"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
    {"type": "message_stop"},
]


def test_provider_passes_contract_suite() -> None:
    client = _Client(_TEXT_EVENTS)
    provider = AnthropicProvider(client_factory=lambda: client)
    run_contract_suite(provider)  # type: ignore[arg-type]


def test_stream_sends_mapped_request_with_stream_flag() -> None:
    client = _Client(_TEXT_EVENTS)
    provider = AnthropicProvider(client_factory=lambda: client)
    req = ModelRequest(
        system="sys",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="claude-test",
        max_output_tokens=32,
    )
    list(provider.stream(req))
    call = client.messages.calls[0]
    assert call["model"] == "claude-test"
    assert call["max_tokens"] == 32
    assert call["stream"] is True


def test_missing_sdk_or_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider()
    req = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    with pytest.raises(ProviderError):
        list(provider.stream(req))
