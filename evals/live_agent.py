"""Run a single evaluation task with the live agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from codeagent.config import load_settings
from codeagent.loop.interrupt import InterruptController
from codeagent.loop.policy import PolicyGate
from codeagent.permissions.approvals import ApprovalPrompt
from codeagent.permissions.run_context import PermissionRun
from codeagent.providers.factory import build_managed_provider
from codeagent.runtime.bootstrap import build_system_prompt, build_tool_registry
from codeagent.state.session import begin_persisted_run, run_with_persistence
from codeagent.state.store import StateStore, default_state_db_path
from codeagent.tools.registry import ToolRegistry
from evals.task_validate import apply_broken, load_task, run_check

EVAL_REPO_ROOT = Path(__file__).resolve().parents[1]

SEARCH_TOOLS = frozenset(
    {
        "read_file",
        "list_dir",
        "glob",
        "grep",
        "git_status",
        "git_diff",
        "git_log",
        "git_show",
    },
)


@dataclass(frozen=True)
class LiveTaskMetrics:
    task_id: str
    ok: bool
    model_calls: int
    search_calls: int
    total_tool_calls: int
    tokens: int
    error: str | None = None


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "eval@codeagent.local"],
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "eval"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "eval baseline", "--allow-empty"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def run_live_task(
    task_dir: Path,
    *,
    max_iterations: int = 12,
    auto_approve: bool = True,
) -> LiveTaskMetrics:
    """Copy a fixture, apply broken overlay, run the agent, return check metrics."""
    task = load_task(task_dir)
    task_id = str(task.get("id", task_dir.name))
    goal = str(task.get("goal", task_id))
    with tempfile.TemporaryDirectory(prefix="codeagent-eval-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(task_dir, work)
        apply_broken(work)
        _init_git_repo(work)
        settings = load_settings(EVAL_REPO_ROOT)
        eval_model = os.environ.get("CODEAGENT_EVAL_MODEL", "").strip()
        if eval_model:
            settings = settings.model_copy(
                update={"model": settings.model.model_copy(update={"main": eval_model})},
            )
        store = StateStore(default_state_db_path(work))
        interrupt = InterruptController()
        try:
            provider, model = build_managed_provider(
                settings,
                EVAL_REPO_ROOT,
                store=store,
            )
            ctx = begin_persisted_run(
                store,
                repo_root=work,
                goal=goal,
                model=model,
                settings=settings,
            )
            registry = build_tool_registry(
                workspace=work,
                repo_root=work,
                settings=settings,
                store=store,
                run_id=ctx.run_id,
                warn=lambda _msg: None,
            )
            _slim_eval_tools(registry)
            policy = PolicyGate(
                run=PermissionRun(workspace=work, settings=settings, interactive=True),
                registry=registry,
                approval_prompt=ApprovalPrompt(choice="session"),
            )
            system = build_system_prompt(work, settings)
            result = run_with_persistence(
                goal,
                provider,
                registry,
                ctx,
                max_iterations=max_iterations,
                interrupt=interrupt,
                system=system,
                max_output_tokens=settings.request.max_output_tokens,
                policy=policy,
            )
            ok = run_check(work) == 0
            model_calls = len(store.list_steps(ctx.run_id))
            tool_rows = store.list_tool_calls(ctx.run_id)
            search_calls = sum(1 for row in tool_rows if str(row["tool"]) in SEARCH_TOOLS)
            tokens = 0
            for step in store.list_steps(ctx.run_id):
                tokens += int(step["tokens_in"] or 0) + int(step["tokens_out"] or 0)
            error = None if ok else f"stop={result.stop_reason}"
            return LiveTaskMetrics(
                task_id=task_id,
                ok=ok,
                model_calls=model_calls,
                search_calls=search_calls,
                total_tool_calls=len(tool_rows),
                tokens=tokens,
                error=error,
            )
        finally:
            store.close()


def _slim_eval_tools(registry: ToolRegistry) -> None:
    """Drop workflow and git tools to keep live eval requests small."""
    for name in (
        "run_command",
        "bash",
        "git_status",
        "git_diff",
        "git_log",
        "git_show",
        "run_verification",
        "run_tests",
        "update_plan",
        "move_path",
        "delete_path",
    ):
        registry._specs.pop(name, None)
        registry._models.pop(name, None)
        registry._handlers.pop(name, None)


def empty_registry(workspace: Path) -> ToolRegistry:
    """Expose registry builder for tests without running the agent."""
    registry = ToolRegistry()
    registry.register_filesystem_tools(workspace)
    return registry
