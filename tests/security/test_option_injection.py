"""Security: read-only tools must not pass model text to a subprocess as options."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from codeagent.config import ToolSettings
from codeagent.tools.file_tools import GrepArgs, handle_grep
from codeagent.tools.git_tools import GitShowArgs, GitToolContext, handle_git_show
from codeagent.tools.workspace_context import WorkspaceToolContext


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agent@test")
    _git(path, "config", "user.name", "Agent")
    (path / "a.txt").write_text("hello\n", encoding="utf-8")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-m", "init")
    return path


@pytest.mark.parametrize("flag", ["--output={target}", "--no-patch"])
def test_git_show_treats_dash_ref_as_revision(tmp_path: Path, flag: str) -> None:
    repo = _repo(tmp_path / "repo")
    target = tmp_path / "written-by-git.txt"
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    result = handle_git_show(ctx, GitShowArgs(ref=flag.format(target=target)))
    assert not result.ok
    assert not target.exists()


def test_git_show_still_shows_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    ctx = GitToolContext(repo=repo, settings=ToolSettings())
    result = handle_git_show(ctx, GitShowArgs(ref="HEAD"))
    assert result.ok
    assert "a.txt" in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
def test_grep_pattern_starting_with_dash_is_a_pattern(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("use --pre=echo here\n", encoding="utf-8")
    ctx = WorkspaceToolContext(workspace=tmp_path, settings=ToolSettings())
    result = handle_grep(ctx, GrepArgs(pattern="--pre=echo", path="."))
    assert result.ok
    assert "use --pre=echo here" in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
def test_grep_path_starting_with_dash_is_a_path(tmp_path: Path) -> None:
    odd = tmp_path / "--files"
    odd.mkdir()
    (odd / "inner.txt").write_text("needle\n", encoding="utf-8")
    (tmp_path / "outer.txt").write_text("nothing\n", encoding="utf-8")
    ctx = WorkspaceToolContext(workspace=tmp_path, settings=ToolSettings())
    result = handle_grep(ctx, GrepArgs(pattern="needle", path="--files"))
    assert result.ok
    assert "inner.txt" in result.content
    assert "outer.txt" not in result.content
