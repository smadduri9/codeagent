"""A resumed run goes back into its own worktree, never the user's checkout."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.config import IsolationSettings
from codeagent.isolation import session as isolation_session
from codeagent.isolation.session import begin_isolation, finish_isolation
from codeagent.lifecycle import RunPhase
from codeagent.providers.base import (
    ModelEvent,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.state.store import StateStore, default_state_db_path


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)
    return done.stdout


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agent@test")
    _git(path, "config", "user.name", "Agent")
    (path / ".gitignore").write_text(".codeagent/\n", encoding="utf-8")
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-m", "init")
    return path


def test_resume_isolation_recreates_the_worktree_from_the_saved_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    first = begin_isolation(repo, "rs-1", IsolationSettings(mode="worktree"))
    (first.workspace / "one.py").write_text("one = 1\n", encoding="utf-8")
    finish_isolation(first)

    second = isolation_session.resume_isolation(repo, "rs-1")
    assert second is not None
    assert (second.workspace / "one.py").read_text(encoding="utf-8") == "one = 1\n"
    (second.workspace / "two.py").write_text("two = 2\n", encoding="utf-8")
    finish_isolation(second)

    assert _git(repo, "show", "codeagent/rs-1:one.py") == "one = 1\n"
    assert _git(repo, "show", "codeagent/rs-1:two.py") == "two = 2\n"
    assert not (repo / "one.py").exists()
    assert not (repo / "two.py").exists()
    assert second.baseline_ref == first.baseline_ref


def test_resume_isolation_after_a_run_that_changed_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    finish_isolation(begin_isolation(repo, "rs-2", IsolationSettings(mode="worktree")))
    again = isolation_session.resume_isolation(repo, "rs-2")
    assert again is not None
    assert (again.workspace / "README.md").exists()
    assert again.workspace != repo
    again.cleanup()


def test_resume_isolation_reuses_a_worktree_left_by_a_crash(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    crashed = begin_isolation(repo, "rs-3", IsolationSettings(mode="worktree"))
    (crashed.workspace / "partial.py").write_text("p = 1\n", encoding="utf-8")
    crashed.lock.release()  # the process died; only the lock went with it

    again = isolation_session.resume_isolation(repo, "rs-3")
    assert again is not None
    assert again.workspace == crashed.workspace
    assert (again.workspace / "partial.py").exists()
    again.cleanup()


def test_resume_isolation_returns_none_for_a_run_without_isolation(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    assert isolation_session.resume_isolation(repo, "never-isolated") is None


def _script(path: Path, filename: str) -> Path:
    write = ToolCall(id="c1", name="write_file", args={"path": filename, "content": "x = 1\n"})
    done: list[ModelEvent] = [
        TextDelta(text="done"),
        UsageEvent(usage=Usage(input=1, output=1)),
        Stop(reason=StopReason.STOP),
    ]
    script: list[list[ModelEvent]] = [
        [
            ToolCallStart(id="c1", name="write_file"),
            ToolCallEnd(call=write),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.TOOL_CALLS),
        ],
        done,
        done,
    ]
    path.write_bytes(TypeAdapter(list[list[ModelEvent]]).dump_json(script))
    return path


def test_cli_resume_writes_into_the_run_branch_not_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    runner = CliRunner()
    first = _script(tmp_path / "first.json", "one.py")
    runner.invoke(app, ["run", "start", "--persist", "--fake-script", str(first)])
    branch = _git(repo, "branch", "--list", "codeagent/*", "--format=%(refname:short)").strip()
    run_id = branch.removeprefix("codeagent/")

    # Mark the run as interrupted so it is resumable.
    store = StateStore(default_state_db_path(repo))
    store.finish_run(run_id, phase=RunPhase.STOPPED, stop_reason="interrupt", status="stopped")
    store.close()

    second = _script(tmp_path / "second.json", "two.py")
    result = runner.invoke(app, ["resume", run_id, "--fake-script", str(second)])

    assert _git(repo, "show", f"{branch}:one.py") == "x = 1\n", result.stderr
    assert _git(repo, "show", f"{branch}:two.py") == "x = 1\n", result.stderr
    assert not (repo / "one.py").exists()
    assert not (repo / "two.py").exists()
    assert _git(repo, "status", "--porcelain") == ""
    assert branch in result.stderr
