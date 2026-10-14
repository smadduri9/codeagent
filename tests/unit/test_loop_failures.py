"""A failed tool result emits failure.classified with the classifier's class."""

import json
from pathlib import Path

from pydantic import BaseModel

from codeagent.loop import run_agent_loop
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


class _NoArgs(BaseModel):
    pass


def _failing(_args: BaseModel) -> ToolResult:
    return ToolResult(
        ok=False,
        summary="failed",
        content="AssertionError: expected 2 got 3",
        truncated=False,
    )


def test_failed_tool_emits_failure_classified(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    emitter = build_run_emitter(store, run_id, tmp_path)
    recorder = RunRecorder(store, run_id, tmp_path, emitter=emitter)
    registry = ToolRegistry()
    registry.register(
        "broken",
        "Always fails (test tool).",
        _NoArgs,
        _failing,
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="broken"),
                ToolCallEnd(call=ToolCall(id="c1", name="broken", args={})),
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
    run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        recorder=recorder,
        run_id=run_id,
    )
    events = [e for e in store.list_events(run_id) if e.name == "failure.classified"]
    assert len(events) == 1
    payload = json.loads(events[0].payload_json or "{}")
    assert payload["tool"] == "broken"
    assert payload["class"] == "UNRECOVERABLE"
    store.close()
