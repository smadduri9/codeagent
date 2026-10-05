"""Operator commands for persisted runs and the repository run lock."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from codeagent.config import find_git_root
from codeagent.isolation.lock import RunLock
from codeagent.lifecycle import RunPhase
from codeagent.state.store import StateStore, default_state_db_path

console = Console(stderr=True)
runs_app = typer.Typer(help="Inspect or repair persisted runs.", no_args_is_help=True)


@runs_app.command("unlock")
def unlock_command(
    force: Annotated[
        bool,
        typer.Option("--force", help="Remove the lock even if the holder PID is alive."),
    ] = False,
) -> None:
    """Remove a stale ``.codeagent/run.lock`` when no agent process is running."""
    root = find_git_root(Path.cwd())
    path = RunLock.lock_path(root)
    if not path.exists():
        console.print("no run lock present")
        raise typer.Exit(0)
    if RunLock.release_stale(root, force=force):
        console.print(f"removed run lock at {path}")
        raise typer.Exit(0)
    console.print(
        "run lock is held by a live process; use --force only if you are sure no run is active",
    )
    raise typer.Exit(1)


@runs_app.command("cancel")
def cancel_command(
    run_id: Annotated[str, typer.Argument(help="Run id to mark cancelled.")],
) -> None:
    """Mark an active run cancelled in SQLite (does not remove the run lock)."""
    root = find_git_root(Path.cwd())
    store = StateStore(default_state_db_path(root))
    try:
        store.connect()
        run = store.get_run(run_id)
        if run is None:
            raise typer.BadParameter(f"unknown run: {run_id}")
        if run.status != "active":
            console.print(
                f"run {run_id} is already {run.status} (phase={run.phase}); nothing to cancel",
            )
            raise typer.Exit(0)
        store.finish_run(
            run_id,
            phase=RunPhase.CANCELLED,
            stop_reason="operator_cancel",
            status="finished",
        )
        console.print(f"cancelled run {run_id}")
    finally:
        store.close()
