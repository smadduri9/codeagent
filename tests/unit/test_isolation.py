"""Worktree isolation, lock, and branch fallback."""

import subprocess
from pathlib import Path

import pytest

from codeagent.config import IsolationSettings
from codeagent.isolation import begin_isolation
from codeagent.isolation.lock import RunLock, RunLockError
from codeagent.isolation.session import DirtyTreeChoice, IsolationError


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


def test_run_lock_refuses_second_run(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    first = RunLock.acquire(tmp_path, "run-a")
    try:
        with pytest.raises(RunLockError):
            RunLock.acquire(tmp_path, "run-b")
    finally:
        first.release()
    second = RunLock.acquire(tmp_path, "run-b")
    second.release()


def test_worktree_leaves_user_tree_unchanged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    marker = tmp_path / "tracked.txt"
    before = marker.read_text(encoding="utf-8")
    session = begin_isolation(tmp_path, "iso-1", IsolationSettings(mode="worktree"))
    try:
        (session.workspace / "tracked.txt").write_text("changed in worktree\n", encoding="utf-8")
        assert marker.read_text(encoding="utf-8") == before
    finally:
        session.cleanup()


def test_branch_mode_aborts_on_dirty_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("wip\n", encoding="utf-8")
    settings = IsolationSettings(mode="branch")
    with pytest.raises(IsolationError):
        begin_isolation(tmp_path, "iso-2", settings)


def test_branch_mode_proceed_records_baseline(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("wip\n", encoding="utf-8")
    settings = IsolationSettings(mode="branch")

    def choose(_msg: str) -> DirtyTreeChoice:
        return DirtyTreeChoice.PROCEED

    session = begin_isolation(tmp_path, "iso-3", settings, on_dirty=choose)
    try:
        assert session.baseline_ref
        assert session.mode == "branch"
        assert (tmp_path / "dirty.txt").read_text(encoding="utf-8") == "wip\n"
    finally:
        session.cleanup()


def test_worktree_fallback_to_branch_when_add_fails(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(
        tmp_path,
        "iso-4",
        IsolationSettings(mode="worktree"),
        force_branch=True,
    )
    try:
        assert session.mode == "branch"
    finally:
        session.cleanup()
