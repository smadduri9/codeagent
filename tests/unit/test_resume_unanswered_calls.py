"""Rebuilt history answers every tool call, so the provider accepts a resumed run."""

from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.lifecycle import RunPhase
from codeagent.permissions import Allow
from codeagent.permissions.types import RiskLevel
from codeagent.providers.base import Message, MessageRole, ToolCall
from codeagent.state.history import rebuild_history
from codeagent.state.session import begin_persisted_run, prepare_resume
from codeagent.state.store import StateStore


def _interrupted_batch(tmp_path: Path, *, finished: int) -> tuple[StateStore, str]:
    """A step with three tool calls where only ``finished`` of them completed."""
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(store, repo_root=tmp_path, goal="g", model="m", settings=Settings())
    calls = [ToolCall(id=f"c{n}", name="read_file", args={"path": f"{n}.py"}) for n in range(3)]
    step_id = store.insert_step(
        ctx.run_id,
        idx=0,
        assistant=Message(role=MessageRole.ASSISTANT, content=None, tool_calls=calls),
        tokens_in=1,
        tokens_out=1,
        cache_read=0,
        cost_usd=0.0,
        latency_ms=1,
    )
    for call in calls[:finished]:
        row = store.begin_tool_call(
            ctx.run_id, step_id, call, Allow(risk_level=RiskLevel.READ_ONLY)
        )
        store.complete_tool_call(row, ok=True, result_content="file body", duration_ms=1)
    store.finish_run(ctx.run_id, phase=RunPhase.STOPPED, stop_reason="interrupt", status="stopped")
    return store, ctx.run_id


def _unanswered(history: list[Message]) -> list[str]:
    answered = {m.tool_call_id for m in history if m.role is MessageRole.TOOL}
    asked = [c.id for m in history if m.role is MessageRole.ASSISTANT for c in m.tool_calls]
    return [call_id for call_id in asked if call_id not in answered]


@pytest.mark.parametrize("finished", [0, 1, 2])
def test_rebuilt_history_answers_calls_that_never_ran(tmp_path: Path, finished: int) -> None:
    store, run_id = _interrupted_batch(tmp_path, finished=finished)
    history = rebuild_history(store, run_id)
    assert _unanswered(history) == []
    tool_ids = [m.tool_call_id for m in history if m.role is MessageRole.TOOL]
    assert tool_ids == ["c0", "c1", "c2"]
    store.close()


def test_prepare_resume_history_is_complete(tmp_path: Path) -> None:
    store, run_id = _interrupted_batch(tmp_path, finished=1)
    _ctx, history, _warnings = prepare_resume(store, run_id, settings=Settings())
    assert _unanswered(history) == []
    placeholder = [m for m in history if m.tool_call_id == "c2"][0]
    assert "not executed" in (placeholder.content or "")
    store.close()


def test_fully_answered_step_is_unchanged(tmp_path: Path) -> None:
    store, run_id = _interrupted_batch(tmp_path, finished=3)
    history = rebuild_history(store, run_id)
    assert [m.tool_call_id for m in history if m.role is MessageRole.TOOL] == ["c0", "c1", "c2"]
    assert all(m.content == "file body" for m in history if m.role is MessageRole.TOOL)
    store.close()
