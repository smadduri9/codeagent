"""Tests for tool registry validation and truncation."""

import pytest

from codeagent.providers.base import ToolCall
from codeagent.tools.registry import ToolRegistry, ToolValidationError, UnknownToolError
from codeagent.tools.truncate import truncate_content


def test_malformed_arguments_never_invoke_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ToolRegistry()
    called = False

    def boom(_: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(registry, "run_validated", boom)
    call = ToolCall(id="1", name="echo", args={"message": 123})
    with pytest.raises(ToolValidationError):
        registry.validate(call)
    assert called is False


def test_unknown_tool_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(UnknownToolError):
        registry.lookup("missing")


def test_echo_tool_runs() -> None:
    registry = ToolRegistry()
    result = registry.run(ToolCall(id="1", name="echo", args={"message": "hi"}))
    assert result.ok is True
    assert result.content == "hi"


def test_truncate_keeps_tail_with_marker() -> None:
    content = "x" * 100
    truncated, was_truncated = truncate_content(content, max_chars=80, keep="tail")
    assert was_truncated is True
    assert "narrow the search]" in truncated
    assert truncated.count("x") < len(content)


def test_truncate_keeps_head_with_marker() -> None:
    content = "x" * 100
    truncated, was_truncated = truncate_content(content, max_chars=80, keep="head")
    assert was_truncated is True
    assert truncated.startswith("x")
