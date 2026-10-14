"""file.changed and budget.warning events."""

import json
from pathlib import Path

from pydantic import BaseModel

from codeagent.config import Settings
from codeagent.loop import run_agent_loop
from codeagent.loop.budget import BudgetTracker
from codeagent.loop.limits import RunLimits
from codeagent.observability.run_emitter import build_run_emitter
from codeagent.providers.base import (
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
from codeagent.state.recorder import RunRecorder
from codeagent.state.store import StateStore
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import ToolRegistry


class _WriteArgs(BaseModel):
    path: str
    content: str


def _write_ok(args: BaseModel) -> ToolResult:
    return ToolResult(ok=True, summary="wrote", content="ok", truncated=False)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "write_file",
        "Write a file (test tool).",
        _WriteArgs,
        _write_ok,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    )
    return registry


def test_successful_write_emits_file_changed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    recorder = RunRecorder(
        store, run_id, tmp_path, emitter=build_run_emitter(store, run_id, tmp_path)
    )
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="write_file"),
                ToolCallEnd(
                    call=ToolCall(
                        id="c1",
                        name="write_file",
                        args={"path": "a.py", "content": "x"},
                    ),
                ),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.TOOL_CALLS),
            ],
            [
                TextDelta(text="done"),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.STOP),
            ],
        ],
    )
    run_agent_loop("g", provider, _registry(), max_iterations=5, recorder=recorder, run_id=run_id)
    changed = [e for e in store.list_events(run_id) if e.name == "file.changed"]
    assert len(changed) == 1
    assert json.loads(changed[0].payload_json or "{}") == {"tool": "write_file", "path": "a.py"}
    store.close()


def test_budget_warns_once_at_eighty_percent() -> None:
    limits = RunLimits.from_settings(Settings(), "m")
    tracker = BudgetTracker(limits=limits)
    tracker.tool_calls = int(limits.max_tool_calls * 0.85)
    first = tracker.warnings()
    assert [w["limit"] for w in first] == ["tool_calls"]
    assert first[0]["max"] == limits.max_tool_calls
    assert tracker.warnings() == []
