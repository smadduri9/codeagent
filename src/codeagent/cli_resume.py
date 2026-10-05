"""Resume a persisted run from SQLite state."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter
from rich.console import Console

from codeagent.cli_output import CliRunOutputRenderer
from codeagent.config import ConfigError, find_git_root, load_settings
from codeagent.loop.interrupt import InterruptController, install_sigint_handler
from codeagent.providers.base import ModelEvent
from codeagent.providers.factory import build_managed_provider
from codeagent.providers.fake import FakeProvider
from codeagent.providers.protocol import Provider
from codeagent.runtime.bootstrap import build_policy_gate, build_system_prompt, build_tool_registry
from codeagent.state.session import prepare_resume, run_with_persistence
from codeagent.state.store import StateStore, default_state_db_path

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
    max_iterations: Annotated[int | None, typer.Option("--max-iterations")] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Auto-approve Ask-tier tools (non-interactive)."),
    ] = False,
) -> None:
    """Continue a stopped run using persisted history."""
    repo_root = find_git_root(Path.cwd())
    settings = load_settings(Path.cwd())
    store = StateStore(default_state_db_path(repo_root))
    interrupt = InterruptController()
    install_sigint_handler(interrupt)
    interactive = not yes and fake_script is None
    try:
        ctx, history, warnings = prepare_resume(store, run_id, settings=settings)
        run = store.get_run(run_id)
        if run is None:
            raise typer.BadParameter(f"unknown run: {run_id}")
        for warning in warnings:
            console.print(f"[yellow]warning[/yellow]: {warning}")
        if fake_script is not None:
            provider: Provider = FakeProvider(load_fake_script(fake_script))
            scripted = True
        else:
            try:
                provider, _model = build_managed_provider(settings, Path.cwd(), store=store)
            except ConfigError as exc:
                raise typer.BadParameter(str(exc)) from exc
            scripted = False
        workspace = Path(run.repo_path)
        registry = build_tool_registry(
            workspace=workspace,
            repo_root=repo_root,
            settings=settings,
            store=store,
            run_id=run_id,
            warn=lambda msg: console.print(f"[bold red]{msg}[/bold red]"),
        )
        policy = build_policy_gate(
            workspace=workspace,
            settings=settings,
            registry=registry,
            interactive=interactive,
            scripted=scripted,
        )
        system = build_system_prompt(repo_root, settings)
        iterations = max_iterations or settings.limits.max_iterations
        renderer = CliRunOutputRenderer(console=console)
        result = run_with_persistence(
            run.goal,
            provider,
            registry,
            ctx,
            max_iterations=iterations,
            history=history,
            interrupt=interrupt,
            resume_warnings=warnings,
            system=system,
            max_output_tokens=settings.request.max_output_tokens,
            policy=policy,
            output=renderer,
        )
    finally:
        store.close()

    renderer.print_final_answer(result.history)
    console.print(f"[bold]stop[/bold]: {result.stop_reason}")
    console.print(f"[bold]iterations[/bold]: {result.iterations}")
    if result.exhaustion_report is not None:
        console.print(result.exhaustion_report.work_accomplished)
    raise typer.Exit(code=0 if result.stop_reason in {"stop", "completed"} else 1)
