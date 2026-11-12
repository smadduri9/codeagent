"""Repeat guard: an edit between identical calls is progress, and the model sees the warning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from codeagent.config import ToolSettings
from codeagent.loop.guards import LoopGuards
from codeagent.loop.runner import run_agent_loop
from codeagent.providers.base import (
    MessageRole,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
)
from codeagent.providers.fake import FakeProvider
from codeagent.tools.registry import ToolRegistry

_XFAIL = pytest.mark.xfail(strict=True, reason="FIX-06")

_TEST_CALL = ToolCall(id="t", name="echo", args={"message": "run the tests"})


def _turn(call: ToolCall) -> list[Any]:
    return [
        ToolCallStart(id=call.id, name=call.name),
        ToolCallEnd(call=call),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


def _done() -> list[Any]:
    return [TextDelta(text="done"), Stop(reason=StopReason.STOP)]


@_XFAIL
def test_guard_window_restarts_after_a_workspace_change() -> None:
    guards = LoopGuards(max_iterations=50)
    for _ in range(6):
        guards.on_workspace_changed()
        result = guards.on_tool_call(_TEST_CALL)
        assert not result.stop
        assert result.warning is None


def test_guard_still_warns_then_stops_without_changes() -> None:
    guards = LoopGuards(max_iterations=50)
    results = [guards.on_tool_call(_TEST_CALL) for _ in range(4)]
    assert results[2].warning is not None
    assert not results[2].stop
    assert results[3].stop


@_XFAIL
def test_edit_then_test_loop_is_not_a_repeat(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path, ToolSettings())
    turns: list[list[Any]] = []
    for index in range(5):
        write = ToolCall(
            id=f"w{index}",
            name="write_file",
            args={"path": f"attempt_{index}.py", "content": f"x = {index}\n"},
        )
        turns.append(_turn(write))
        turns.append(_turn(_TEST_CALL))
    turns.append(_done())
    result = run_agent_loop("fix it", FakeProvider(turns), registry, max_iterations=20)
    assert result.stop_reason != "repeat_tool_calls"
    assert result.guard_warning is None


def test_failed_edit_does_not_restart_the_window(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path, ToolSettings())
    (tmp_path / "exists.py").write_text("x = 1\n", encoding="utf-8")
    failing_write = ToolCall(
        id="w", name="write_file", args={"path": "exists.py", "content": "x = 2\n"}
    )
    turns: list[list[Any]] = []
    for _ in range(4):
        turns.append(_turn(failing_write))
        turns.append(_turn(_TEST_CALL))
    result = run_agent_loop("fix it", FakeProvider(turns), registry, max_iterations=20)
    assert result.stop_reason == "repeat_tool_calls"


@_XFAIL
def test_model_is_told_about_the_repeat_warning() -> None:
    turns = [_turn(_TEST_CALL), _turn(_TEST_CALL), _turn(_TEST_CALL), _done()]
    result = run_agent_loop("repeat", FakeProvider(turns), ToolRegistry(), max_iterations=20)
    warnings = [
        message
        for message in result.history
        if message.role is MessageRole.USER and "identical tool call" in (message.content or "")
    ]
    assert len(warnings) == 1
    assert result.history[-1].content == "done"
