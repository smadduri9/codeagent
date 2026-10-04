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


def _session_workspace(git_root: Path, run_id: str) -> Path:
    meta = git_root / ".codeagent" / "runs" / run_id / "session.json"
    if not meta.exists():
        raise typer.BadParameter(f"unknown run_id: {run_id}")
    payload = json.loads(meta.read_text(encoding="utf-8"))
    worktree = payload.get("worktree_path")
    if worktree:
        return Path(worktree)
    return git_root


def rollback_command(
    run_id: Annotated[str, typer.Argument(help="Run identifier from isolation.")],
    to: Annotated[
        str | None,
        typer.Option("--to", help="Checkpoint label; default is earliest recorded."),
    ] = None,
) -> None:
    """Reset the isolated workspace to a checkpoint (never pushes)."""
    git_root = find_git_root(Path.cwd())
    workspace = _session_workspace(git_root, run_id)
    store = CheckpointStore.load(git_root, run_id, workspace=workspace)
    try:
        ref = store.rollback_to(to)
    except RollbackError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[bold]rolled back[/bold] run {run_id} to {ref}")
    status = run_git(workspace, ["status", "--short"], check=False)
    if status.stdout.strip():
        console.print(status.stdout.rstrip())
