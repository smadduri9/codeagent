"""Spans wrap the run, each model call and each tool call."""

from pathlib import Path

from codeagent.config import Settings
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


def _span_rows(store: StateStore, run_id: str) -> dict[str, list[tuple[str, str | None]]]:
    """Map event name to (span_id, parent_span_id) rows, in insertion order."""
    rows: dict[str, list[tuple[str, str | None]]] = {}
    cursor = store.connect().execute(
        "SELECT name, span_id, parent_span_id FROM events WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    for name, span_id, parent in cursor.fetchall():
        rows.setdefault(name, []).append((span_id, parent))
    return rows


def test_run_model_and_tool_spans_form_a_tree(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(
        store,
        repo_root=tmp_path,
        goal="trace",
        model="m",
        settings=Settings(),
    )
    result = run_with_persistence(
        "trace",
        _echo_script(),
        ToolRegistry(),
        ctx,
        max_iterations=5,
    )
    assert result.stop_reason == StopReason.STOP.value
    rows = _span_rows(store, ctx.run_id)

    run_span = rows["run.start"][0][0]
    assert rows["run.start"][0][1] is None
    assert rows["run.end"][0][0] == run_span

    model_starts = rows["model.call.start"]
    assert len(model_starts) == 2
    assert all(parent == run_span for _span, parent in model_starts)

    tool_start = rows["tool.call.start"][0]
    assert tool_start[1] == run_span
    assert rows["tool.call.end"][0][0] == tool_start[0]
    store.close()
