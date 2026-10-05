"""Persisted run recording tests."""

from pathlib import Path

from codeagent.lifecycle import RunPhase
from codeagent.loop.runner import run_agent_loop
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
from codeagent.tools.registry import ToolRegistry


def test_persist_run_records_steps_and_tools(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="persist me", model="m")
    recorder = RunRecorder(store, run_id, tmp_path)
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="echo"),
                ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "ok"})),
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
    registry = ToolRegistry()
    result = run_agent_loop(
        "persist me",
        provider,
        registry,
        max_iterations=5,
        recorder=recorder,
        run_id=run_id,
    )
    recorder.finish(RunPhase.COMPLETED, result.stop_reason)
    assert result.stop_reason == StopReason.STOP.value
    assert len(store.list_steps(run_id)) == 2
    tools = store.list_tool_calls(run_id)
    assert len(tools) == 1
    assert tools[0]["decision"] == "allow"
    assert tools[0]["ok"] == 1
    store.close()
