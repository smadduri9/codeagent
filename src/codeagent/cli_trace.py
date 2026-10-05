import json
from pathlib import Path

import typer
from rich.console import Console

from codeagent.config import find_git_root
from codeagent.observability.reconstruct import reconstruct_run, trace_jsonl_path
from codeagent.state.store import StateStore, default_state_db_path

console = Console()


def trace_command(run_id: str) -> None:
    root = find_git_root(Path.cwd())
    store = StateStore(default_state_db_path(root))
    store.connect()
    try:
        run = store.get_run(run_id)
        if run is None:
            console.print(f"unknown run: {run_id}")
            raise typer.Exit(1)
        timeline = reconstruct_run(store, run_id, repo_root=root)
        if not timeline:
            console.print(
                f"run {run_id}: phase={run.phase} status={run.status} "
                f"stop_reason={run.stop_reason or '-'}",
            )
            steps = store.list_steps(run_id)
            if steps:
                console.print(
                    f"no trace events in SQLite or {trace_jsonl_path(root, run_id)}; "
                    f"{len(steps)} step(s) recorded in state.db",
                )
            else:
                console.print(
                    "no trace events recorded yet "
                    f"(checked events table and {trace_jsonl_path(root, run_id)})",
                )
            raise typer.Exit(0)
        for entry in timeline:
            console.print(
                f"{entry['ts']} {entry['name']} {json.dumps(entry.get('payload'))}",
            )
    finally:
        store.close()
