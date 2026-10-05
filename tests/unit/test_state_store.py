"""SQLite store and migration tests."""

import sqlite3
from pathlib import Path

from codeagent.lifecycle import RunPhase
from codeagent.permissions.types import Allow, RiskLevel
from codeagent.providers.base import Message, MessageRole, ToolCall
from codeagent.state.migrations import apply_migrations, current_schema_version
from codeagent.state.store import StateStore


def test_migrations_apply_on_empty_database(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    version = apply_migrations(conn)
    assert version == 2
    assert current_schema_version(conn) == 2
    conn.close()


def test_migrations_apply_on_existing_database(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    apply_migrations(conn)
    conn.close()
    conn = sqlite3.connect(db)
    assert apply_migrations(conn) == 2
    conn.close()


def test_create_load_update_run(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(
        repo_path=tmp_path,
        goal="test goal",
        model="test-model",
    )
    loaded = store.get_run(run_id)
    assert loaded is not None
    assert loaded.goal == "test goal"
    assert loaded.phase == RunPhase.INITIALIZING.value

    store.update_run_phase(run_id, RunPhase.WORKING)
    assistant = Message(role=MessageRole.ASSISTANT, content="hi")
    step_id = store.insert_step(
        run_id,
        idx=0,
        assistant=assistant,
        tokens_in=3,
        tokens_out=2,
        cache_read=0,
        cost_usd=0.0,
        latency_ms=10,
    )
    tool_id = store.begin_tool_call(
        run_id,
        step_id,
        ToolCall(id="c1", name="echo", args={"message": "x"}),
        Allow(risk_level=RiskLevel.READ_ONLY),
    )
    row = store.list_tool_calls(run_id)[0]
    assert row["decision"] == "allow"
    assert row["ok"] is None

    store.complete_tool_call(tool_id, ok=True, result_content="ok", duration_ms=5)
    row = store.list_tool_calls(run_id)[0]
    assert row["ok"] == 1

    store.finish_run(run_id, phase=RunPhase.COMPLETED, stop_reason="stop")
    finished = store.get_run(run_id)
    assert finished is not None
    assert finished.phase == RunPhase.COMPLETED.value
    assert finished.stop_reason == "stop"
    store.close()
