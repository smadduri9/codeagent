"""Checkpoints, rollback, and final diff (no push)."""

import subprocess
from pathlib import Path

import pytest

from codeagent.config import IsolationSettings
from codeagent.isolation import begin_isolation, format_final_diff
from codeagent.isolation.checkpoint import RollbackError
from codeagent.isolation.git_wrapper import run_git


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agent@test")
    _git(path, "config", "user.name", "Agent")
    (path / "file.txt").write_text("v1\n", encoding="utf-8")
    _git(path, "add", "file.txt")
    _git(path, "commit", "-m", "init")


def test_rollback_restores_checkpoint(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(tmp_path, "cp-1", IsolationSettings(mode="branch"), force_branch=True)
    store = session.checkpoints
    start = store.create("start")
    (session.workspace / "file.txt").write_text("v2\n", encoding="utf-8")
    store.create("after-edit")
    store.rollback_to("start")
    assert (session.workspace / "file.txt").read_text(encoding="utf-8") == "v1\n"
    assert start.git_ref
    session.cleanup()


def test_rollback_unknown_label(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(tmp_path, "cp-2", IsolationSettings(mode="branch"), force_branch=True)
    store = session.checkpoints
    store.create("only")
    with pytest.raises(RollbackError):
        store.rollback_to("missing")
    session.cleanup()


def test_no_automatic_push(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    remotes = run_git(tmp_path, ["remote"], check=False)
    assert remotes.stdout.strip() == ""
    session = begin_isolation(tmp_path, "cp-3", IsolationSettings(mode="branch"), force_branch=True)
    (session.workspace / "file.txt").write_text("v2\n", encoding="utf-8")
    session.checkpoints.create("edit")
    _ = format_final_diff(session.workspace, session.baseline_ref)
    session.cleanup()
    remotes_after = run_git(tmp_path, ["remote"], check=False)
    assert remotes_after.stdout.strip() == ""


def test_final_diff_includes_changes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(tmp_path, "cp-4", IsolationSettings(mode="branch"), force_branch=True)
    (session.workspace / "file.txt").write_text("v2\n", encoding="utf-8")
    _git(session.workspace, "add", "file.txt")
    _git(session.workspace, "commit", "-m", "change")
    text = format_final_diff(session.workspace, session.baseline_ref)
    assert "file.txt" in text
    session.cleanup()
