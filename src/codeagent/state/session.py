"""Begin, persist, and resume agent runs through the state store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeagent.config import Settings
from codeagent.lifecycle import LifecycleState, RunPhase
from codeagent.loop.budget import BudgetTracker
from codeagent.loop.interrupt import InterruptController
from codeagent.loop.limits import RunLimits
from codeagent.loop.policy import PolicyGate
from codeagent.loop.runner import RunResult, run_agent_loop
from codeagent.providers.base import Message
from codeagent.providers.protocol import Provider
from codeagent.state.history import rebuild_history
from codeagent.state.recorder import RunRecorder
from codeagent.state.resume import reconcile_files_read, stale_read_paths
from codeagent.state.store import RunRecord, StateStore
from codeagent.tools.registry import ToolRegistry

RESUMABLE_STOP_REASONS = frozenset(
    {
        "interrupt",
        "max_total_tokens",
        "max_cost_usd",
        "max_tool_calls",
        "max_runtime_minutes",
        "waiting_quota",
    },
)


@dataclass(frozen=True, slots=True)
class PersistedRunContext:
    store: StateStore
    run_id: str
    repo_root: Path
    recorder: RunRecorder
    lifecycle: LifecycleState
    limits: RunLimits
    budget: BudgetTracker


def begin_persisted_run(
    store: StateStore,
    *,
    repo_root: Path,
    goal: str,
    model: str,
    settings: Settings,
    run_id: str | None = None,
) -> PersistedRunContext:
    rid = store.create_run(
        repo_path=repo_root,
        goal=goal,
        model=model,
        config_json=settings.model_dump_json(),
        run_id=run_id,
    )
    limits = RunLimits.from_settings(settings, model)
    lifecycle = LifecycleState()
    recorder = RunRecorder(
        store,
        rid,
        repo_root,
        _step_index=store.next_step_index(rid),
    )
    return PersistedRunContext(
        store=store,
        run_id=rid,
        repo_root=repo_root,
        recorder=recorder,
        lifecycle=lifecycle,
        limits=limits,
        budget=BudgetTracker(limits=limits),
    )


def can_resume_run(run: RunRecord) -> bool:
    if run.phase in {
        RunPhase.COMPLETED.value,
        RunPhase.COMPLETED_UNVERIFIED.value,
        RunPhase.FAILED.value,
        RunPhase.CANCELLED.value,
    }:
        return False
    if run.status == "finished":
        return False
    if run.stop_reason in RESUMABLE_STOP_REASONS:
        return True
    return run.phase == RunPhase.WAITING_QUOTA.value


def prepare_resume(
    store: StateStore,
    run_id: str,
    *,
    settings: Settings | None = None,
) -> tuple[PersistedRunContext, list[Message], list[str]]:
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")
    if not can_resume_run(run):
        raise ValueError(f"run {run_id} is not resumable")

    repo_root = Path(run.repo_path)
    model = run.model or "test-model"
    if settings is None and run.config_json:
        settings = Settings.model_validate_json(run.config_json)
    if settings is None:
        settings = Settings()

    limits = RunLimits.from_settings(settings, model)
    lifecycle = LifecycleState(phase=RunPhase.INITIALIZING)
    recorder = RunRecorder(
        store,
        run_id,
        repo_root,
        _step_index=store.next_step_index(run_id),
    )
    warnings = reconcile_files_read(store, run_id, repo_root)
    stale = stale_read_paths(store, run_id, repo_root)
    if stale:
        warnings.append(
            "stale file reads (re-read before relying on content): " + ", ".join(stale),
        )

    history = rebuild_history(store, run_id)
    store.update_run_phase(run_id, RunPhase.WORKING)
    ctx = PersistedRunContext(
        store=store,
        run_id=run_id,
        repo_root=repo_root,
        recorder=recorder,
        lifecycle=lifecycle,
        limits=limits,
        budget=BudgetTracker(limits=limits),
    )
    return ctx, history, warnings


def run_with_persistence(
    goal: str,
    provider: Provider,
    registry: ToolRegistry,
    ctx: PersistedRunContext,
    *,
    max_iterations: int | None = None,
    history: list[Message] | None = None,
    interrupt: InterruptController | None = None,
    resume_warnings: list[str] | None = None,
    max_output_chars: int = 8000,
    system: str | None = None,
    max_output_tokens: int | None = None,
    policy: PolicyGate | None = None,
) -> RunResult:
    iterations = max_iterations if max_iterations is not None else ctx.limits.max_iterations
    if history is None and ctx.recorder._step_index > 0:
        history = rebuild_history(ctx.store, ctx.run_id)

    loop_system = system if system is not None else "You are a coding agent."
    loop_tokens = max_output_tokens if max_output_tokens is not None else 256

    return run_agent_loop(
        goal,
        provider,
        registry,
        max_iterations=iterations,
        max_output_chars=max_output_chars,
        system=loop_system,
        model=ctx.limits.model,
        max_output_tokens=loop_tokens,
        store=ctx.store,
        run_id=ctx.run_id,
        repo_root=ctx.repo_root,
        history=history,
        lifecycle=ctx.lifecycle,
        recorder=ctx.recorder,
        limits=ctx.limits,
        budget=ctx.budget,
        interrupt=interrupt,
        resume_warnings=resume_warnings,
        policy=policy,
    )
