"""Read-only git tools in temporary repositories."""

import subprocess
from pathlib import Path

from codeagent.config import ToolSettings
from codeagent.tools.git_tools import (
    GitDiffArgs,
    GitLogArgs,
    GitShowArgs,
    GitStatusArgs,
    GitToolContext,
    handle_git_diff,
    handle_git_log,
    handle_git_show,
    handle_git_status,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agent@test")
    _git(path, "config", "user.name", "Agent")


def test_git_status_no_commits(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    result = handle_git_status(ctx, GitStatusArgs())
    assert result.ok
    assert "main" in result.content


def test_git_log_empty_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    result = handle_git_log(ctx, GitLogArgs())
    assert result.ok
    assert result.content == ""


def test_git_diff_dirty_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "init")
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    diff = handle_git_diff(ctx, GitDiffArgs())
    assert diff.ok
    assert "two" in diff.content or "-one" in diff.content


def test_git_show_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README").write_text("hi\n", encoding="utf-8")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "init")
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    show = handle_git_show(ctx, GitShowArgs())
    assert show.ok
    assert "init" in show.content
