"""In worktree mode every tool looks at the worktree, not the user's checkout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from codeagent.config import IsolationSettings, Settings, VerifySettings
from codeagent.isolation.session import begin_isolation
from codeagent.providers.base import ToolCall
from codeagent.runtime.bootstrap import build_tool_registry
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry

# Passes only when run from a directory that contains marker.txt.
_NEEDS_MARKER = [
    sys.executable,
    "-c",
    "import pathlib, sys; sys.exit(0 if pathlib.Path('marker.txt').exists() else 1)",
]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _registry(tmp_path: Path) -> tuple[ToolRegistry, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "agent@test")
    _git(repo, "config", "user.name", "Agent")
    (repo / ".gitignore").write_text(".codeagent/\n", encoding="utf-8")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    settings = Settings(verify=VerifySettings(test=_NEEDS_MARKER))
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(
        repo_path=repo, goal="g", model="m", config_json=settings.model_dump_json()
    )
    session = begin_isolation(repo, run_id, IsolationSettings(mode="worktree"))
    registry = build_tool_registry(
        workspace=session.workspace,
        repo_root=repo,
        settings=settings,
        store=store,
        run_id=run_id,
        warn=lambda _msg: None,
    )
    return registry, repo, session.workspace


def _run(registry: ToolRegistry, name: str, args: dict[str, object]) -> str:
    result = registry.run(ToolCall(id="1", name=name, args=args))
    return f"{result.ok}|{result.content}"


def test_git_tools_see_worktree_changes(tmp_path: Path) -> None:
    registry, _repo, worktree = _registry(tmp_path)
    (worktree / "README.md").write_text("edited by the agent\n", encoding="utf-8")
    (worktree / "added.py").write_text("x = 1\n", encoding="utf-8")
    assert "added.py" in _run(registry, "git_status", {})
    assert "edited by the agent" in _run(registry, "git_diff", {})


def test_run_tests_runs_in_the_worktree(tmp_path: Path) -> None:
    registry, _repo, worktree = _registry(tmp_path)
    (worktree / "marker.txt").write_text("here\n", encoding="utf-8")
    outcome = _run(registry, "run_tests", {})
    assert outcome.startswith("True|")
    assert "test:pass" in outcome


def test_run_tests_does_not_pass_on_the_untouched_checkout(tmp_path: Path) -> None:
    registry, repo, _worktree = _registry(tmp_path)
    (repo / "marker.txt").write_text("only in the user's checkout\n", encoding="utf-8")
    outcome = _run(registry, "run_tests", {})
    assert outcome.startswith("False|")
    assert "test:fail" in outcome
