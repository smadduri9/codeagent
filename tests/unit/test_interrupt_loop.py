"""Interrupt handling leaves resumable state."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.loop.interrupt import InterruptController
from codeagent.loop.runner import run_agent_loop
from codeagent.providers.base import (
    Stop,
    StopReason,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.state.recorder import RunRecorder
from codeagent.state.session import can_resume_run, prepare_resume
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry


def test_interrupt_after_tool_persists_resumable_state(tmp_path: Path) -> None:
    registry = ToolRegistry()
    interrupt = InterruptController()
    script = [
        [
            ToolCallStart(id="c1", name="echo"),
            ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "ok"})),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.TOOL_CALLS),
        ],
        [
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.STOP),
        ],
    ]
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    recorder = RunRecorder(store, run_id, tmp_path)
    provider = FakeProvider(script)
    base_run = registry.run

    def run_then_signal(call: ToolCall):
        result = base_run(call)
        interrupt.on_signal()
        return result

    registry.run = run_then_signal  # type: ignore[method-assign]
    result = run_agent_loop(
        "g",
        provider,
        registry,
        max_iterations=5,
        recorder=recorder,
        run_id=run_id,
        interrupt=interrupt,
    )
    assert result.stop_reason == "interrupt"
    run = store.get_run(run_id)
    assert run is not None
    assert can_resume_run(run)
    _ctx, history, _warnings = prepare_resume(store, run_id, settings=Settings())
    assert len(history) >= 2
    assert store.list_tool_calls(run_id)[0]["ok"] == 1
    store.close()


def test_second_interrupt_is_immediate() -> None:
    interrupt = InterruptController()
    interrupt.on_signal()
    interrupt.on_signal()
    assert interrupt.immediate is True
    assert interrupt.should_stop_before_tool() is True
