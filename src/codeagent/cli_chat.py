"""Interactive chat REPL for CodeAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter
from rich.console import Console
from rich.prompt import Prompt

from codeagent.cli_bootstrap import ensure_workspace, validate_live_run
from codeagent.cli_output import CliRunOutputRenderer
from codeagent.cli_run import execute_agent_run
from codeagent.config import ConfigError, load_settings
from codeagent.loop.interrupt import InterruptController, install_sigint_handler
from codeagent.providers.base import Message, MessageRole, ModelEvent

console = Console(stderr=True)

_EXIT_WORDS = frozenset({"exit", "quit", "/exit"})


def load_fake_script(path: Path) -> list[list[ModelEvent]]:
    adapter = TypeAdapter(list[list[ModelEvent]])
    return adapter.validate_json(path.read_text())


def _read_goal() -> str | None:
    try:
        line = Prompt.ask("[bold cyan]you[/bold cyan]", console=console).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not line:
        return ""
    if line.lower() in _EXIT_WORDS:
        return None
    return line


def chat_command(
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Auto-approve Ask-tier tools (non-interactive)."),
    ] = False,
    fake_script: Annotated[
        Path | None,
        typer.Option("--fake-script", hidden=True, help="Replay scripted provider turns."),
    ] = None,
) -> None:
    """Start an interactive session in the current Git repository."""
    cwd = Path.cwd()
    try:
        repo_root = ensure_workspace(cwd)
    except ConfigError as exc:
        console.print(f"[bold red]error[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    scripted = fake_script is not None
    if not scripted:
        try:
            validate_live_run(cwd)
        except ConfigError as exc:
            console.print(f"[bold red]error[/bold red]: {exc}")
            raise typer.Exit(code=1) from exc

    settings = load_settings(cwd)
    interrupt = InterruptController()
    install_sigint_handler(interrupt)
    interactive = not yes and not scripted

    console.print(
        "[bold]CodeAgent[/bold] — describe a goal, or type "
        "[dim]exit[/dim] / [dim]quit[/dim] / [dim]/exit[/dim] (Ctrl+D to leave)."
    )
    console.print(f"[dim]repo[/dim] {repo_root}")

    history: list[Message] | None = None
    session_goal: str | None = None

    while True:
        goal = _read_goal()
        if goal is None:
            console.print("[dim]bye[/dim]")
            break
        if not goal:
            continue

        if session_goal is None:
            session_goal = goal
        if history is not None:
            history = list(history)
            history.append(Message(role=MessageRole.USER, content=goal))
        else:
            history = [Message(role=MessageRole.USER, content=goal)]

        renderer = CliRunOutputRenderer(console=console)
        try:
            result = execute_agent_run(
                goal=session_goal,
                cwd=cwd,
                repo_root=repo_root,
                settings=settings,
                fake_script=fake_script,
                interactive=interactive,
                interrupt=interrupt,
                output=renderer,
                history=history,
            )
        except typer.Exit as exc:
            raise exc
        except ConfigError as exc:
            console.print(f"[bold red]error[/bold red]: {exc}")
            raise typer.Exit(code=1) from exc

        history = list(result.history)
        renderer.print_final_answer(history)
        console.print(
            f"[dim]stop[/dim] {result.stop_reason} · [dim]iterations[/dim] {result.iterations}"
        )
        if result.stop_reason not in {"stop", "completed", "completed_unverified"}:
            console.print("[yellow]session ended after a non-success stop[/yellow]")
            break
