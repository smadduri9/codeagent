"""Resume a persisted run from SQLite state."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter
from rich.console import Console

from codeagent.config import find_git_root, load_settings
from codeagent.loop.interrupt import InterruptController, install_sigint_handler
from codeagent.providers.base import ModelEvent
from codeagent.providers.fake import FakeProvider
from codeagent.state.session import prepare_resume, run_with_persistence
from codeagent.state.store import StateStore, default_state_db_path
from codeagent.tools.registry import ToolRegistry

console = Console(stderr=True)


def load_fake_script(path: Path) -> list[list[ModelEvent]]:
    adapter = TypeAdapter(list[list[ModelEvent]])
    return adapter.validate_json(path.read_text())


def resume_command(
    run_id: Annotated[str, typer.Argument(help="Run id to resume.")],
    fake_script: Annotated[
        Path | None,
        typer.Option("--fake-script", hidden=True, help="Replay scripted provider turns."),
    ] = None,
    max_iterations: Annotated[int, typer.Option("--max-iterations")] = 10,
) -> None:
    """Continue a stopped run using persisted history."""
    if fake_script is None:
        raise typer.BadParameter("--fake-script is required until live providers are wired")
    repo_root = find_git_root(Path.cwd())
    settings = load_settings(Path.cwd())
    store = StateStore(default_state_db_path(repo_root))
    interrupt = InterruptController()
    install_sigint_handler(interrupt)
    try:
        ctx, history, warnings = prepare_resume(store, run_id, settings=settings)
        run = store.get_run(run_id)
        if run is None:
            raise typer.BadParameter(f"unknown run: {run_id}")
        for warning in warnings:
            console.print(f"[yellow]warning[/yellow]: {warning}")
        provider = FakeProvider(load_fake_script(fake_script))
        registry = ToolRegistry()
        result = run_with_persistence(
            run.goal,
            provider,
            registry,
            ctx,
            max_iterations=max_iterations,
            history=history,
            interrupt=interrupt,
            resume_warnings=warnings,
        )
    finally:
        store.close()

    console.print(f"[bold]stop[/bold]: {result.stop_reason}")
    console.print(f"[bold]iterations[/bold]: {result.iterations}")
    if result.exhaustion_report is not None:
        console.print(result.exhaustion_report.work_accomplished)
    raise typer.Exit(code=0 if result.stop_reason in {"stop", "completed"} else 1)
