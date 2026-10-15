"""Run the agent live on the SWE-bench subset with Haiku under a hard spend cap.

Usage:
  python -m evals.swebench_live --out .codeagent/swebench/runs/<name> --cap 3.0 [--ids a,b]
      [--no-compaction] [--max-iterations 20]

The agent never sees the test patch. After the run, any edits it made to the
patched test files are reverted, the test patch is applied, and the failing tests
run in the task's own environment. Exit 0 means solved.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from evals.swebench_env import build_env, pytest_args

from codeagent.config import LimitSettings, PermissionSettings, RequestSettings, Settings
from codeagent.context.manager import ContextManager
from codeagent.loop.policy import PolicyGate
from codeagent.permissions.run_context import PermissionRun
from codeagent.providers.anthropic import AnthropicProvider
from codeagent.runtime.bootstrap import build_system_prompt
from codeagent.state.session import begin_persisted_run, run_with_persistence
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry
from evals.spend import HAIKU, SpendGuardProvider, SpendLedger
from evals.swebench import SweInstance, load_instances

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".codeagent" / "swe_bench_lite_test.jsonl"
SWE = ROOT / ".codeagent" / "swebench"
MIN_REMAINING_USD = 0.10
MAX_OUTPUT_TOKENS = 2000


@dataclass
class TaskResult:
    instance_id: str
    solved: bool
    stop_reason: str
    model_calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    seconds: float
    diff_lines: int
    test_exit: int | None
    compaction: bool
    error: str | None = None


def goal_text(inst: SweInstance) -> str:
    return (
        f"You are working in a checkout of {inst.repo}. Resolve this issue:\n\n"
        f"{inst.problem_statement}\n\n"
        "Make the smallest change to the library code that fixes the issue. "
        "Do not edit or add tests; they are run separately after you finish. "
        "You can run `python -m pytest <path>` to check your work."
    )


def eval_settings(max_iterations: int) -> Settings:
    return Settings(
        permissions=PermissionSettings(extra_allow=["python", "pytest"]),
        request=RequestSettings(max_request_tokens=30_000, max_output_tokens=MAX_OUTPUT_TOKENS),
        limits=LimitSettings(
            max_iterations=max_iterations,
            max_tool_calls=60,
            max_total_tokens=600_000,
            max_cost_usd=0.0,
            max_runtime_minutes=20,
        ),
    )


def _git(args: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, input=stdin, capture_output=True, text=True, check=False
    )


def patched_test_files(test_patch: str) -> list[str]:
    return [line[len("+++ b/") :] for line in test_patch.splitlines() if line.startswith("+++ b/")]


def restore_and_apply_tests(workspace: Path, test_patch: str) -> bool:
    """Undo the agent's edits to patched test files, then apply the test patch."""
    for rel in patched_test_files(test_patch):
        tracked = _git(["ls-files", "--error-unmatch", rel], workspace).returncode == 0
        if tracked:
            _git(["checkout", "--", rel], workspace)
        else:
            (workspace / rel).unlink(missing_ok=True)
    return _git(["apply", "-"], workspace, stdin=test_patch).returncode == 0


def _registry(workspace: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_filesystem_tools(workspace)
    registry.register_command_tools(workspace)
    for name in ("bash", "move_path", "delete_path"):  # run_command only: no shell strings
        registry._specs.pop(name, None)
        registry._models.pop(name, None)
        registry._handlers.pop(name, None)
    return registry


def run_task(
    inst: SweInstance,
    *,
    out_dir: Path,
    ledger: SpendLedger,
    max_iterations: int,
    compaction: bool,
) -> TaskResult:
    clone = SWE / "repos" / inst.repo.replace("/", "__")
    workspace = SWE / "work" / inst.instance_id
    task_out = out_dir / inst.instance_id
    task_out.mkdir(parents=True, exist_ok=True)
    if workspace.exists():
        _git(["worktree", "remove", "--force", str(workspace)], clone)
    _git(["worktree", "add", "--detach", str(workspace), inst.base_commit], clone)
    python = build_env(inst, workspace, SWE / "envs" / inst.instance_id)

    settings = eval_settings(max_iterations)
    guard = SpendGuardProvider(
        AnthropicProvider(thinking={"type": "disabled"}, start_dir=ROOT),
        ledger,
    )
    store = StateStore(task_out / "state.db")
    before = ledger.spent_usd
    started = time.monotonic()
    saved_env = {k: os.environ.get(k) for k in ("PATH", "VIRTUAL_ENV")}
    os.environ["PATH"] = f"{python.parent}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["VIRTUAL_ENV"] = str(python.parent.parent)
    error: str | None = None
    stop_reason = "not_started"
    try:
        goal = goal_text(inst)
        ctx = begin_persisted_run(
            store, repo_root=workspace, goal=goal, model=HAIKU, settings=settings
        )
        registry = _registry(workspace)
        policy = PolicyGate(
            run=PermissionRun(workspace=workspace, settings=settings, interactive=False),
            registry=registry,
        )
        result = run_with_persistence(
            goal,
            guard,
            registry,
            ctx,
            max_iterations=max_iterations,
            system=build_system_prompt(workspace, settings),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            policy=policy,
            context=ContextManager(settings=settings, instructions="") if compaction else None,
        )
        stop_reason = result.stop_reason
        steps = store.list_steps(ctx.run_id)
        tokens_in = sum(int(s["tokens_in"] or 0) for s in steps)
        tokens_out = sum(int(s["tokens_out"] or 0) for s in steps)
    except Exception as exc:  # noqa: BLE001 - one task's failure must not stop the batch
        error = f"{type(exc).__name__}: {exc}"[:500]
        tokens_in = tokens_out = 0
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        store.close()

    diff = _git(["diff"], workspace).stdout
    (task_out / "agent.diff").write_text(diff, encoding="utf-8")
    test_exit: int | None = None
    if restore_and_apply_tests(workspace, inst.test_patch):
        cmd = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", *pytest_args(inst)]
        test = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=900)
        test_exit = test.returncode
        (task_out / "test.log").write_text(test.stdout[-20000:], encoding="utf-8")
    else:
        error = error or "test patch did not apply"
    _git(["worktree", "remove", "--force", str(workspace)], clone)
    return TaskResult(
        instance_id=inst.instance_id,
        solved=test_exit == 0,
        stop_reason=stop_reason,
        model_calls=guard.calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=round(ledger.spent_usd - before, 6),
        seconds=round(time.monotonic() - started, 1),
        diff_lines=sum(1 for line in diff.splitlines() if line[:1] in "+-"),
        test_exit=test_exit,
        compaction=compaction,
        error=error,
    )


def _slice_ids(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cap", type=float, required=True, help="USD cap shared by this --out")
    parser.add_argument("--ids", default="", help="comma-separated subset of the slice")
    parser.add_argument("--slice", type=Path, default=ROOT / "evals" / "slices" / "swe30.txt")
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--no-compaction", action="store_true")
    args = parser.parse_args(argv)

    ids = [i for i in args.ids.split(",") if i] or _slice_ids(args.slice)
    ledger = SpendLedger(args.out / "spend.json", cap_usd=args.cap)
    results_path = args.out / "results.jsonl"
    done = set()
    if results_path.exists():
        done = {json.loads(line)["instance_id"] for line in results_path.read_text().splitlines()}
    for inst in load_instances(DATA, ids):
        if inst.instance_id in done:
            continue
        if ledger.remaining_usd < MIN_REMAINING_USD:
            print(f"stopping: ${ledger.remaining_usd:.4f} left of ${ledger.cap_usd:.2f}")
            break
        result = run_task(
            inst,
            out_dir=args.out,
            ledger=ledger,
            max_iterations=args.max_iterations,
            compaction=not args.no_compaction,
        )
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(result)) + "\n")
        print(
            f"{result.instance_id:32s} solved={result.solved!s:5s} calls={result.model_calls:2d} "
            f"cost=${result.cost_usd:.4f} total=${ledger.spent_usd:.4f} stop={result.stop_reason} "
            f"{result.error or ''}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
