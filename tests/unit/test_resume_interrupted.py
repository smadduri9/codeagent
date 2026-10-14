"""Resume closes tool calls that started but never finished."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.lifecycle import RunPhase
from codeagent.permissions import Allow
from codeagent.permissions.types import RiskLevel
from codeagent.providers.base import Message, MessageRole, ToolCall
from codeagent.state.session import INTERRUPTED_MSG, begin_persisted_run, prepare_resume
from codeagent.state.store import StateStore


def test_interrupted_tool_call_is_closed_on_resume(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(
        store,
        repo_root=tmp_path,
        goal="g",
        model="m",
        settings=Settings(),
    )
    call = ToolCall(id="c1", name="write_file", args={"path": "a.py"})
    step_id = store.insert_step(
        ctx.run_id,
        idx=0,
        assistant=Message(role=MessageRole.ASSISTANT, content=None, tool_calls=[call]),
        tokens_in=1,
        tokens_out=1,
        cache_read=0,
        cost_usd=0.0,
        latency_ms=1,
    )
    tool_row_id = store.begin_tool_call(
        ctx.run_id,
        step_id,
        call,
        Allow(risk_level=RiskLevel.READ_ONLY),
    )
    # A run stopped by Ctrl-C is resumable; a crashed run is not (see PR notes).
    store.finish_run(ctx.run_id, phase=RunPhase.STOPPED, stop_reason="interrupt", status="stopped")
    store.close()

    store = StateStore(tmp_path / "state.db")
    resumed, history, warnings = prepare_resume(store, ctx.run_id, settings=Settings())

    rows = [r for r in store.list_tool_calls(ctx.run_id) if r["id"] == tool_row_id]
    assert rows[0]["ok"] == 0
    assert INTERRUPTED_MSG in (rows[0]["result_json"] or "")
    assert any("write_file" in w and "interrupted" in w for w in warnings)
    tool_results = [m for m in history if m.role is MessageRole.TOOL]
    assert [m.tool_call_id for m in tool_results] == ["c1"]
    resumed.store.close()
