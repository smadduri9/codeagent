"""AnthropicProvider passes the shared contract checks with a fake SDK client."""

import subprocess
import sys
import types
from pathlib import Path
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


def test_missing_key_is_a_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Look only in an empty temporary repo, never the developer's real .env files.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=object))
    provider = AnthropicProvider(start_dir=tmp_path, user_dir=tmp_path / "no-home")
    req = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    with pytest.raises(ProviderError):
        list(provider.stream(req))


def test_key_is_read_from_repo_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-key-not-real\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seen: dict[str, str] = {}

    class _Anthropic:
        def __init__(self, *, api_key: str) -> None:
            seen["key"] = api_key
            self.messages = _Messages(_TEXT_EVENTS)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Anthropic))
    provider = AnthropicProvider(start_dir=tmp_path, user_dir=tmp_path / "no-home")
    req = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    list(provider.stream(req))
    assert seen["key"] == "test-key-not-real"


def test_provider_forwards_thinking_setting() -> None:
    client = _Client(_TEXT_EVENTS)
    provider = AnthropicProvider(client_factory=lambda: client, thinking={"type": "disabled"})
    req = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    list(provider.stream(req))
    assert client.messages.calls[0]["thinking"] == {"type": "disabled"}


def test_workspace_id_is_sent_as_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".env").write_text(
        "ANTHROPIC_API_KEY=test-key-not-real\nANTHROPIC_WORKSPACE_ID=wrkspc_test\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    seen: dict[str, Any] = {}

    class _Anthropic:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)
            self.messages = _Messages(_TEXT_EVENTS)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Anthropic))
    provider = AnthropicProvider(start_dir=tmp_path, user_dir=tmp_path / "no-home")
    req = ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )
    list(provider.stream(req))
    assert seen["default_headers"] == {"anthropic-workspace-id": "wrkspc_test"}
