import json
from pathlib import Path

import typer
from rich.console import Console

from codeagent.config import find_git_root
from codeagent.observability.reconstruct import reconstruct_run
from codeagent.state.store import StateStore, default_state_db_path

console = Console()


def trace_command(run_id: str) -> None:
    root = find_git_root(Path.cwd())
    store = StateStore(default_state_db_path(root))
    store.connect()
    timeline = reconstruct_run(store, run_id)
    if not timeline:
        raise typer.Exit(1)
    for entry in timeline:
        console.print(f"{entry['ts']} {entry['name']} {json.dumps(entry.get('payload'))}")
    store.close()
