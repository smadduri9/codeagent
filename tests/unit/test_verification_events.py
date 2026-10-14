"""verification.* events are derived from verification tool results."""

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


def _verify(_args: BaseModel) -> ToolResult:
    return ToolResult(
        ok=False,
        summary="verification",
        content="pytest:pass\nruff:fail",
        truncated=False,
    )


def test_verification_tool_emits_started_checks_and_completed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    recorder = RunRecorder(
        store, run_id, tmp_path, emitter=build_run_emitter(store, run_id, tmp_path)
    )
    registry = ToolRegistry()
    registry.register(
        "run_verification",
        "Run checks (test tool).",
        _NoArgs,
        _verify,
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="run_verification"),
                ToolCallEnd(call=ToolCall(id="c1", name="run_verification", args={})),
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
    run_agent_loop("g", provider, registry, max_iterations=5, recorder=recorder, run_id=run_id)
    events = [e for e in store.list_events(run_id) if e.name.startswith("verification.")]
    names = [e.name for e in events]
    assert names == [
        "verification.started",
        "verification.check",
        "verification.check",
        "verification.completed",
    ]
    checks = [json.loads(e.payload_json or "{}") for e in events[1:3]]
    assert checks == [
        {"name": "pytest", "status": "pass"},
        {"name": "ruff", "status": "fail"},
    ]
    done = json.loads(events[3].payload_json or "{}")
    assert done == {"passed": 1, "failed": 1}
    store.close()
