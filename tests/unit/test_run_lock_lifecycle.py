"""Run lock acquire, stale recovery, and teardown."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.config import IsolationSettings
from codeagent.isolation.lock import RunLock, RunLockError
from codeagent.isolation.session import begin_isolation, finish_isolation
from codeagent.lifecycle import RunPhase
from codeagent.observability.reconstruct import reconstruct_run, trace_jsonl_path
from codeagent.observability.sink import JsonlEventSink
from codeagent.state.session import abort_persisted_run, begin_persisted_run
from codeagent.state.store import StateStore


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agent@test")
    _git(path, "config", "user.name", "Agent")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-m", "init")


def test_acquire_replaces_dead_pid_lock(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    lock_path = RunLock.lock_path(tmp_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"run_id": "stale", "pid": 9_999_999_999}),
        encoding="utf-8",
    )
    lock = RunLock.acquire(tmp_path, "fresh")
    lock.release()
    assert not lock_path.exists()


def test_release_stale_unlock_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    lock_path = RunLock.lock_path(tmp_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"run_id": "stale", "pid": 9_999_999_999}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["runs", "unlock"])
    assert result.exit_code == 0
    assert not lock_path.exists()


def test_finish_isolation_releases_lock(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(tmp_path, "iso-lock", IsolationSettings(mode="worktree"))
    lock_path = RunLock.lock_path(tmp_path)
    assert lock_path.exists()
    finish_isolation(session)
    assert not lock_path.exists()


def test_live_lock_raises(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    import os

    lock_path = RunLock.lock_path(tmp_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps({"run_id": "live", "pid": os.getpid()}),
        encoding="utf-8",
    )
    with pytest.raises(RunLockError):
        RunLock.acquire(tmp_path, "other")


def test_abort_persisted_run_marks_failed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.connect()
    ctx = begin_persisted_run(
        store,
        repo_root=tmp_path,
        goal="g",
        model="m",
        settings=__import__("codeagent.config", fromlist=["Settings"]).Settings(),
    )
    abort_persisted_run(ctx, "isolation_lock")
    run = store.get_run(ctx.run_id)
    assert run is not None
    assert run.phase == RunPhase.FAILED.value
    assert run.status == "stopped"
    assert run.stop_reason == "isolation_lock"
    store.close()


def test_reconstruct_run_reads_jsonl(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.connect()
    rid = store.create_run(repo_path=tmp_path, goal="g", model="m")
    jsonl = trace_jsonl_path(tmp_path, rid)
    JsonlEventSink(jsonl).write(
        run_id=rid,
        trace_id="t1",
        span_id=None,
        name="run.started",
        payload={"ok": True},
    )
    events = reconstruct_run(store, rid, repo_root=tmp_path)
    assert len(events) == 1
    assert events[0]["name"] == "run.started"
    store.close()


def test_trace_shows_summary_when_no_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repo(tmp_path)
    store = StateStore(tmp_path / ".codeagent" / "state.db")
    store.connect()
    rid = store.create_run(repo_path=tmp_path, goal="goal", model="m")
    store.close()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["trace", rid])
    assert result.exit_code == 0
    assert rid in result.stdout
    assert "no trace events" in result.stdout
