"""A tool or SDK exception is a failed result, never a crashed run (DESIGN 8.12)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import openai
import pytest

from codeagent.config import ToolSettings
from codeagent.loop.runner import run_agent_loop
from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelRequest,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.providers.openai_compatible import OpenAICompatibleProvider
from codeagent.providers.quota_errors import ContextOverflowError, ProviderError
from codeagent.tools.base import StrictArgs, ToolResult
from codeagent.tools.registry import ToolRegistry

_XFAIL = pytest.mark.xfail(strict=True, reason="FIX-04")


class _NoArgs(StrictArgs):
    pass


def _registry_with_raising_tool(exc: Exception) -> ToolRegistry:
    def handler(_args: _NoArgs) -> ToolResult:
        raise exc

    registry = ToolRegistry()
    registry.register("boom", "Always raises (test tool).", _NoArgs, handler)
    return registry


@_XFAIL
@pytest.mark.parametrize(
    "exc",
    [PermissionError("denied by os"), IsADirectoryError("is a directory"), ValueError("bad")],
)
def test_handler_exception_becomes_failed_result(exc: Exception) -> None:
    registry = _registry_with_raising_tool(exc)
    result = registry.run(ToolCall(id="1", name="boom", args={}))
    assert not result.ok
    assert type(exc).__name__ in result.content
    assert str(exc) in result.content


@_XFAIL
def test_read_file_on_non_utf8_text_fails_cleanly(tmp_path: Path) -> None:
    (tmp_path / "latin1.txt").write_bytes("caf\xe9 au lait\n".encode("latin-1"))
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path, ToolSettings())
    result = registry.run(ToolCall(id="1", name="read_file", args={"path": "latin1.txt"}))
    assert not result.ok
    assert "UnicodeDecodeError" in result.content


@_XFAIL
def test_loop_survives_a_raising_tool() -> None:
    turns: list[list[Any]] = [
        [
            ToolCallStart(id="c1", name="boom"),
            ToolCallEnd(call=ToolCall(id="c1", name="boom", args={})),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.TOOL_CALLS),
        ],
        [
            TextDelta(text="done"),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.STOP),
        ],
    ]
    registry = _registry_with_raising_tool(PermissionError("denied by os"))
    result = run_agent_loop("goal", FakeProvider(turns), registry, max_iterations=5)
    assert result.stop_reason != "provider_error"
    assert result.history[-1].content == "done"


def _request() -> ModelRequest:
    return ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        model="m",
        max_output_tokens=8,
    )


def _provider(exc: Exception) -> OpenAICompatibleProvider:
    def factory(**_kwargs: Any) -> Iterator[Any]:
        raise exc

    return OpenAICompatibleProvider(
        base_url="http://127.0.0.1:1", api_key_env="CODEAGENT_TEST_UNSET", stream_factory=factory
    )


@_XFAIL
def test_openai_sdk_error_becomes_provider_error() -> None:
    with pytest.raises(ProviderError, match="Connection error"):
        list(_provider(openai.OpenAIError("Connection error.")).stream(_request()))


def test_request_too_large_is_still_context_overflow() -> None:
    with pytest.raises(ContextOverflowError):
        list(_provider(openai.OpenAIError("Request too large for model")).stream(_request()))


def test_non_sdk_error_is_not_swallowed() -> None:
    with pytest.raises(KeyError):
        list(_provider(KeyError("bug")).stream(_request()))
