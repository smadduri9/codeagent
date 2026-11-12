"""`codeagent rollback` works on a run whose worktree was removed at finish."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.config import IsolationSettings
from codeagent.isolation.session import IsolationSession, begin_isolation, finish_isolation


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)
    return done.stdout.strip()


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


def _finished_run(repo: Path, run_id: str) -> IsolationSession:
    session = begin_isolation(repo, run_id, IsolationSettings(mode="worktree"))
    (session.workspace / "new_feature.py").write_text("x = 1\n", encoding="utf-8")
    finish_isolation(session)
    return session


def test_begin_records_a_baseline_checkpoint(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    session = begin_isolation(repo, "rb-0", IsolationSettings(mode="worktree"))
    try:
        first = session.checkpoints.records[0]
        assert first.label == "baseline"
        assert first.git_ref == session.baseline_ref
    finally:
        session.cleanup()


def test_rollback_of_a_finished_run_resets_its_branch_to_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    _finished_run(repo, "rb-1")
    assert _git(repo, "rev-parse", "codeagent/rb-1") != _git(repo, "rev-parse", "main")
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["rollback", "rb-1"])
    assert result.exit_code == 0, result.stderr
    assert _git(repo, "rev-parse", "codeagent/rb-1") == _git(repo, "rev-parse", "main")
    assert _git(repo, "status", "--porcelain") == ""


def test_rollback_to_the_final_checkpoint_keeps_the_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    _finished_run(repo, "rb-2")
    before = _git(repo, "rev-parse", "codeagent/rb-2")
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["rollback", "rb-2", "--to", "final"])
    assert result.exit_code == 0, result.stderr
    assert _git(repo, "rev-parse", "codeagent/rb-2") == before


def test_rollback_refuses_when_the_run_branch_is_checked_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    _finished_run(repo, "rb-3")
    _git(repo, "switch", "codeagent/rb-3")
    before = _git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["rollback", "rb-3"])
    assert result.exit_code != 0
    assert "checked out" in result.output + result.stderr
    assert _git(repo, "rev-parse", "HEAD") == before


def test_rollback_of_an_unknown_run_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["rollback", "nope"])
    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)
