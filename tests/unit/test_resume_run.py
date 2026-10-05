"""Kill and resume scripted runs."""

from pathlib import Path

from codeagent.config import LimitSettings, Settings
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
from codeagent.state.session import begin_persisted_run, prepare_resume, run_with_persistence
from codeagent.state.store import StateStore
from codeagent.tools.read_tracker import content_hash
from codeagent.tools.registry import ToolRegistry


def _completion_script() -> list[list[object]]:
    return [
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
    ]


def test_resume_run_matches_uninterrupted(tmp_path: Path) -> None:
    settings = Settings()
    registry = ToolRegistry()
    script = _completion_script()

    full = run_agent_loop(
        "goal",
        FakeProvider(script),
        registry,
        max_iterations=5,
    )

    tight = Settings(
        limits=LimitSettings(
            max_iterations=30,
            max_tool_calls=100,
            max_total_tokens=3,
            max_cost_usd=5.0,
            max_runtime_minutes=90,
        ),
    )
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(
        store,
        repo_root=tmp_path,
        goal="goal",
        model="m",
        settings=tight,
        run_id="run-a",
    )
    partial = run_with_persistence(
        "goal",
        FakeProvider(script),
        registry,
        ctx,
        max_iterations=5,
    )
    assert partial.stop_reason == "max_total_tokens"
    partial_run = store.get_run("run-a")
    assert partial_run is not None
    assert partial_run.status == "stopped"

    resume_ctx, history, _warnings = prepare_resume(store, "run-a", settings=settings)
    resumed = run_with_persistence(
        "goal",
        FakeProvider(script[1:]),
        registry,
        resume_ctx,
        max_iterations=5,
        history=history,
    )
    assert resumed.stop_reason == full.stop_reason
    assert len(resumed.history) == len(full.history)
    finished = store.get_run("run-a")
    assert finished is not None
    assert finished.phase == RunPhase.COMPLETED.value
    store.close()


def test_resume_warns_on_external_file_change(tmp_path: Path) -> None:
    settings = Settings()
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    store.finish_run(run_id, phase=RunPhase.WORKING, stop_reason="interrupt", status="stopped")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1", encoding="utf-8")
    store.record_file_read(run_id, tracked.relative_to(tmp_path), content_hash("v1"))
    tracked.write_text("v2", encoding="utf-8")
    _ctx, _history, warnings = prepare_resume(store, run_id, settings=settings)
    assert any("changed externally" in warning for warning in warnings)
    store.close()
