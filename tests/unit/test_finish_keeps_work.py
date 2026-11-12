"""A finished worktree run keeps the agent's work on its branch (DESIGN 8.14)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.config import IsolationSettings
from codeagent.isolation.session import begin_isolation, finish_isolation
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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)


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


def _branch_exists(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def test_finish_commits_work_and_keeps_the_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    session = begin_isolation(repo, "keep-1", IsolationSettings(mode="worktree"))
    worktree = session.workspace
    (worktree / "new_feature.py").write_text("x = 1\n", encoding="utf-8")
    (worktree / "README.md").write_text("hello again\n", encoding="utf-8")

    diff = finish_isolation(session)

    assert "new_feature.py" in diff
    assert "hello again" in diff
    assert _branch_exists(repo, "codeagent/keep-1")
    shown = _git(repo, "show", "codeagent/keep-1:new_feature.py")
    assert shown.stdout == "x = 1\n"
    assert session.saved_branch == "codeagent/keep-1"
    assert not worktree.exists()
    # The user's checkout is untouched.
    assert not (repo / "new_feature.py").exists()
    assert (repo / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_finish_without_changes_leaves_no_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    session = begin_isolation(repo, "keep-2", IsolationSettings(mode="worktree"))
    diff = finish_isolation(session)
    assert "no changes" in diff
    assert not _branch_exists(repo, "codeagent/keep-2")
    assert session.saved_branch is None


def test_finish_keeps_the_worktree_when_the_commit_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    session = begin_isolation(repo, "keep-3", IsolationSettings(mode="worktree"))
    worktree = session.workspace
    (worktree / "new_feature.py").write_text("x = 1\n", encoding="utf-8")
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    finish_isolation(session)

    assert session.saved_branch is None
    assert session.kept_worktree
    assert (worktree / "new_feature.py").read_text(encoding="utf-8") == "x = 1\n"
    assert _branch_exists(repo, "codeagent/keep-3")


def test_finish_releases_the_lock_so_a_second_run_can_start(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    first = begin_isolation(repo, "keep-4", IsolationSettings(mode="worktree"))
    (first.workspace / "a.py").write_text("a = 1\n", encoding="utf-8")
    finish_isolation(first)
    second = begin_isolation(repo, "keep-5", IsolationSettings(mode="worktree"))
    second.cleanup()


def _script(tmp_path: Path) -> Path:
    write = ToolCall(
        id="c1", name="write_file", args={"path": "new_feature.py", "content": "x = 1\n"}
    )
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
    path = tmp_path / "script.json"
    path.write_bytes(TypeAdapter(list[list[ModelEvent]]).dump_json(script))
    return path


def test_persisted_cli_run_keeps_the_written_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(
        app, ["run", "add a feature", "--persist", "--fake-script", str(_script(tmp_path))]
    )
    branches = _git(repo, "branch", "--list", "codeagent/*", "--format=%(refname:short)")
    names = branches.stdout.split()
    assert len(names) == 1, result.stderr
    assert _git(repo, "show", f"{names[0]}:new_feature.py").stdout == "x = 1\n"
    assert "new_feature.py" in result.stderr
    assert names[0] in result.stderr
    assert not (repo / "new_feature.py").exists()
    assert list((repo / ".codeagent" / "worktrees").iterdir()) == []
