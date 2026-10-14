from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codeagent.config import find_git_root
from codeagent.state.store import StateStore, default_state_db_path
from codeagent.stats import compute_stats, stats_as_json

console = Console()


def stats_command(
    run_id: str | None = typer.Argument(None, help="Run id; default is the latest run."),
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of a table."),
) -> None:
    """Show token, cache, latency and tool statistics for a run."""
    root = find_git_root(Path.cwd())
    store = StateStore(default_state_db_path(root))
    store.connect()
    try:
        if run_id is None:
            runs = store.list_runs(limit=1)
            if not runs:
                console.print("no runs recorded")
                raise typer.Exit(1)
            run_id = runs[0].id
        if store.get_run(run_id) is None:
            console.print(f"unknown run: {run_id}")
            raise typer.Exit(1)
        stats = compute_stats(store.list_events(run_id))
    finally:
        store.close()

    if as_json:
        console.print_json(stats_as_json(stats))
        return
    table = Table(title=f"run {run_id}")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("model calls", str(stats.model_calls))
    table.add_row("tool calls", str(stats.tool_calls))
    table.add_row("input tokens", str(stats.input_tokens))
    table.add_row("output tokens", str(stats.output_tokens))
    table.add_row("cache read / write", f"{stats.cache_read_tokens} / {stats.cache_write_tokens}")
    table.add_row("cache hit ratio", f"{stats.cache_hit_ratio:.2%}")
    table.add_row("wall time (ms)", str(stats.wall_ms))
    table.add_row("denied calls", str(stats.denied_calls))
    console.print(table)
    if stats.segment_share:
        seg = Table(title="input share by segment")
        seg.add_column("segment")
        seg.add_column("%", justify="right")
        for name, share in sorted(stats.segment_share.items(), key=lambda x: -x[1]):
            seg.add_row(name, f"{share:.1f}")
        console.print(seg)
