"""CLI run command with streaming output."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter
from rich.console import Console

from codeagent.loop import run_agent_loop
from codeagent.providers.base import ModelEvent
from codeagent.providers.fake import FakeProvider
from codeagent.tools.registry import ToolRegistry

console = Console(stderr=True)


def load_fake_script(path: Path) -> list[list[ModelEvent]]:
    adapter = TypeAdapter(list[list[ModelEvent]])
    return adapter.validate_json(path.read_text())


def run_command(
    goal: Annotated[str, typer.Argument(help="Task goal for the agent.")],
    fake_script: Annotated[
        Path | None,
        typer.Option("--fake-script", hidden=True, help="Replay scripted provider turns."),
    ] = None,
    max_iterations: Annotated[int, typer.Option("--max-iterations")] = 10,
) -> None:
    """Run the agent loop (scripted replay for tests and demos)."""
    if fake_script is None:
        raise typer.BadParameter("--fake-script is required until live providers are wired")
    turns = load_fake_script(fake_script)
    provider = FakeProvider(turns)
    registry = ToolRegistry()
    result = run_agent_loop(
        goal,
        provider,
        registry,
        max_iterations=max_iterations,
    )
    console.print(f"[bold]stop[/bold]: {result.stop_reason}")
    console.print(f"[bold]iterations[/bold]: {result.iterations}")
    raise typer.Exit(code=0 if result.stop_reason in {"stop", "completed"} else 1)
