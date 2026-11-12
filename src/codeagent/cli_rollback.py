"""Rollback command for isolated runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from codeagent.config import find_git_root
from codeagent.isolation.checkpoint import CheckpointStore, RollbackError
from codeagent.isolation.git_wrapper import run_git

console = Console(stderr=True)


def _session_meta(git_root: Path, run_id: str) -> dict[str, object]:
    meta = git_root / ".codeagent" / "runs" / run_id / "session.json"
    if not meta.exists():
        raise typer.BadParameter(f"unknown run_id: {run_id}")
    payload: dict[str, object] = json.loads(meta.read_text(encoding="utf-8"))
    return payload


def _rollback_saved_branch(git_root: Path, run_id: str, branch: str, to: str | None) -> None:
    """Move a finished run's branch; its worktree no longer exists."""
    store = CheckpointStore.load(git_root, run_id, workspace=git_root)
    try:
        ref = store.resolve(to)
    except RollbackError as exc:
        raise typer.BadParameter(str(exc)) from exc
    full = f"refs/heads/{branch}"
    if run_git(git_root, ["rev-parse", "--verify", "--quiet", full], check=False).returncode != 0:
        raise typer.BadParameter(f"run {run_id} has no saved branch; nothing to roll back")
    current = run_git(git_root, ["branch", "--show-current"], check=False).stdout.strip()
    if current == branch:
        raise typer.BadParameter(
            f"branch {branch} is checked out; switch away or reset it yourself with git"
        )
    run_git(git_root, ["update-ref", full, ref], check=True)
    console.print(f"moved branch {branch} to {ref}", markup=False, highlight=False)


def rollback_command(
    run_id: Annotated[str, typer.Argument(help="Run identifier from isolation.")],
    to: Annotated[
        str | None,
        typer.Option("--to", help="Checkpoint label; default is earliest recorded."),
    ] = None,
) -> None:
    """Reset the isolated workspace to a checkpoint (never pushes)."""
    git_root = find_git_root(Path.cwd())
    meta = _session_meta(git_root, run_id)
    worktree = meta.get("worktree_path")
    if isinstance(worktree, str) and not Path(worktree).exists():
        _rollback_saved_branch(git_root, run_id, str(meta.get("branch_name", "")), to)
        return
    workspace = Path(worktree) if isinstance(worktree, str) else git_root
    store = CheckpointStore.load(git_root, run_id, workspace=workspace)
    try:
        ref = store.rollback_to(to)
    except RollbackError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[bold]rolled back[/bold] run {run_id} to {ref}")
    status = run_git(workspace, ["status", "--short"], check=False)
    if status.stdout.strip():
        console.print(status.stdout.rstrip())
