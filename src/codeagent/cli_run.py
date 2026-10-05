"""CLI run command with streaming output."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import TypeAdapter
from rich.console import Console

from codeagent.config import ConfigError, find_git_root, load_settings
from codeagent.isolation.session import DirtyTreeChoice, begin_isolation
from codeagent.loop import run_agent_loop
from codeagent.loop.interrupt import InterruptController, install_sigint_handler
from codeagent.providers.base import ModelEvent
from codeagent.providers.factory import build_managed_provider
from codeagent.providers.fake import FakeProvider
from codeagent.providers.protocol import Provider
from codeagent.runtime.bootstrap import build_policy_gate, build_system_prompt, build_tool_registry
from codeagent.state.session import begin_persisted_run, run_with_persistence
from codeagent.state.store import StateStore, default_state_db_path

console = Console(stderr=True)


def load_fake_script(path: Path) -> list[list[ModelEvent]]:
    adapter = TypeAdapter(list[list[ModelEvent]])
    return adapter.validate_json(path.read_text())


def _resolve_provider(
    *,
    cwd: Path,
    fake_script: Path | None,
    store: StateStore | None,
) -> tuple[Provider, str, bool]:
    settings = load_settings(cwd)
    if fake_script is not None:
        model = settings.model.main or "test-model"
        return FakeProvider(load_fake_script(fake_script)), model, True
    provider, model = build_managed_provider(settings, cwd, store=store)
    return provider, model, False


def run_command(
    goal: Annotated[str, typer.Argument(help="Task goal for the agent.")],
    fake_script: Annotated[
        Path | None,
        typer.Option("--fake-script", hidden=True, help="Replay scripted provider turns."),
    ] = None,
    max_iterations: Annotated[int | None, typer.Option("--max-iterations")] = None,
    persist: Annotated[
        bool, typer.Option("--persist", help="Persist run state to SQLite.")
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Auto-approve Ask-tier tools (non-interactive)."),
    ] = False,
) -> None:
    """Run the agent loop against the configured Groq model (or a fake script)."""
    cwd = Path.cwd()
    repo_root = find_git_root(cwd)
    settings = load_settings(cwd)
    interactive = not yes and fake_script is None
    interrupt = InterruptController()
    install_sigint_handler(interrupt)
    isolation = None
    store: StateStore | None = None

    try:
        if persist:
            store = StateStore(default_state_db_path(repo_root))
        try:
            provider, model, scripted = _resolve_provider(
                cwd=cwd,
                fake_script=fake_script,
                store=store,
            )
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

        workspace = repo_root
        run_id: str | None = None
        ctx = None
        if persist:
            assert store is not None
            ctx = begin_persisted_run(
                store,
                repo_root=repo_root,
                goal=goal,
                model=model,
                settings=settings,
            )
            run_id = ctx.run_id

            def on_dirty(_msg: str) -> DirtyTreeChoice:
                if interactive:
                    answer = (
                        typer.prompt(
                            "Uncommitted changes; proceed on branch? [y/N]",
                            default="n",
                        )
                        .strip()
                        .lower()
                    )
                    if answer in {"y", "yes"}:
                        return DirtyTreeChoice.PROCEED
                return DirtyTreeChoice.ABORT

            isolation = begin_isolation(
                repo_root,
                run_id,
                settings.isolation,
                on_dirty=on_dirty if interactive else None,
            )
            workspace = isolation.workspace

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
        max_output = settings.request.max_output_tokens

        if persist:
            assert store is not None and ctx is not None
            result = run_with_persistence(
                goal,
                provider,
                registry,
                ctx,
                max_iterations=iterations,
                interrupt=interrupt,
                system=system,
                max_output_tokens=max_output,
                policy=policy,
            )
            console.print(f"[bold]run_id[/bold]: {ctx.run_id}")
        else:
            result = run_agent_loop(
                goal,
                provider,
                registry,
                max_iterations=iterations,
                system=system,
                model=model,
                max_output_tokens=max_output,
                policy=policy,
                repo_root=repo_root,
                interrupt=interrupt,
            )
    finally:
        if store is not None:
            store.close()

    if isolation is not None:
        diff = isolation.finish()
        if diff.strip():
            console.print("[bold]final diff[/bold]:")
            console.print(diff)

    console.print(f"[bold]stop[/bold]: {result.stop_reason}")
    console.print(f"[bold]iterations[/bold]: {result.iterations}")
    if result.exhaustion_report is not None:
        console.print(result.exhaustion_report.work_accomplished)
    raise typer.Exit(code=0 if result.stop_reason in {"stop", "completed"} else 1)
