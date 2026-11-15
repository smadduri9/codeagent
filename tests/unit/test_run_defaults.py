"""`codeagent run` is isolated by default; --no-persist is the explicit opt-out."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from codeagent.cli import app
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

_XFAIL = pytest.mark.xfail(strict=True, reason="FIX-11")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)
    return done.stdout


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "agent@test")
    _git(repo, "config", "user.name", "Agent")
    (repo / ".gitignore").write_text(".codeagent/\n", encoding="utf-8")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    monkeypatch.chdir(repo)
    return repo


def _script(tmp_path: Path) -> str:
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
    return str(path)


def _branches(repo: Path) -> list[str]:
    return _git(repo, "branch", "--list", "codeagent/*", "--format=%(refname:short)").split()


@_XFAIL
def test_run_is_isolated_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    result = CliRunner().invoke(app, ["run", "add a feature", "--fake-script", _script(tmp_path)])
    assert not (repo / "new_feature.py").exists(), result.stderr
    branches = _branches(repo)
    assert len(branches) == 1
    assert _git(repo, "show", f"{branches[0]}:new_feature.py") == "x = 1\n"
    assert "run_id" in result.stderr


@_XFAIL
def test_no_persist_edits_the_checkout_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        app, ["run", "add a feature", "--no-persist", "--fake-script", _script(tmp_path)]
    )
    assert (repo / "new_feature.py").read_text(encoding="utf-8") == "x = 1\n", result.stderr
    assert _branches(repo) == []
    assert not (repo / ".codeagent" / "state.db").exists()


@_XFAIL
def test_isolated_run_says_uncommitted_changes_are_not_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    (repo / "README.md").write_text("edited but not committed\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["run", "add a feature", "--fake-script", _script(tmp_path)])
    assert "uncommitted changes" in result.stderr
    assert (repo / "README.md").read_text(encoding="utf-8") == "edited but not committed\n"


def test_clean_checkout_gets_no_uncommitted_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        app, ["run", "add a feature", "--persist", "--fake-script", _script(tmp_path)]
    )
    assert "uncommitted changes" not in result.stderr


@_XFAIL
def test_help_documents_the_opt_out() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])
    assert "--no-persist" in result.output
