"""Show persisted run status."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from codeagent.config import find_git_root
from codeagent.state.store import StateStore, default_state_db_path

console = Console(stderr=True)


def status_command(
    run_id: Annotated[str | None, typer.Argument(help="Optional run id.")] = None,
) -> None:
    """Print phase and stop reason for recent or selected runs."""
    repo_root = find_git_root(Path.cwd())
    store = StateStore(default_state_db_path(repo_root))
    try:
        if run_id is not None:
            run = store.get_run(run_id)
            if run is None:
                raise typer.BadParameter(f"unknown run: {run_id}")
            console.print(f"run {run.id}: phase={run.phase} status={run.status}")
            if run.stop_reason:
                console.print(f"stop_reason={run.stop_reason}")
            steps = len(store.list_steps(run.id))
            tools = len(store.list_tool_calls(run.id))
            console.print(f"steps={steps} tool_calls={tools}")
            raise typer.Exit(code=0)

        table = Table("run_id", "phase", "status", "goal")
        for run in store.list_runs():
            goal = run.goal if len(run.goal) <= 48 else run.goal[:45] + "..."
            table.add_row(run.id, run.phase, run.status, goal)
        console.print(table)
    finally:
        store.close()
