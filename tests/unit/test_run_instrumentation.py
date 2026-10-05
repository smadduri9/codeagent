"""Trace events during persisted agent runs."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.lifecycle import RunPhase
from codeagent.loop.runner import run_agent_loop
from codeagent.observability.reconstruct import reconstruct_run, trace_jsonl_path
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
from codeagent.state.session import begin_persisted_run, run_with_persistence
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry


def _echo_script() -> FakeProvider:
    return FakeProvider(
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


def test_persisted_run_writes_trace_events(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(
        store,
        repo_root=tmp_path,
        goal="trace me",
        model="m",
        settings=__import__("codeagent.config", fromlist=["Settings"]).Settings(),
    )
    registry = ToolRegistry()
    result = run_with_persistence(
        "trace me",
        _echo_script(),
        registry,
        ctx,
        max_iterations=5,
    )
    assert result.stop_reason == StopReason.STOP.value

    names = [e.name for e in store.list_events(ctx.run_id)]
    assert "run.started" in names
    assert "model.request" in names
    assert "model.response" in names
    assert "tool.requested" in names
    assert "tool.completed" in names
    assert "run.completed" in names

    jsonl = trace_jsonl_path(tmp_path, ctx.run_id)
    assert jsonl.is_file()
    timeline = reconstruct_run(store, ctx.run_id, repo_root=tmp_path)
    assert len(timeline) >= len(names)
    store.close()


def test_recorder_emitter_writes_jsonl_and_db(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    emitter = build_run_emitter(store, run_id, tmp_path)
    recorder = RunRecorder(store, run_id, tmp_path, emitter=emitter)
    provider = _echo_script()
    registry = ToolRegistry()
    run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        recorder=recorder,
        run_id=run_id,
    )
    recorder.finish(RunPhase.COMPLETED, StopReason.STOP.value)

    assert store.list_events(run_id)
    assert trace_jsonl_path(tmp_path, run_id).is_file()
    store.close()
