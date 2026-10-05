from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from codeagent.config import Settings
from codeagent.state.store import StateStore
from codeagent.tools.base import StrictArgs, ToolResult
from codeagent.verification.checks import VerificationCheck
from codeagent.verification.pipeline import VerificationPipeline


class RunVerificationArgs(StrictArgs):
    scope: str | None = None


class RunTestsArgs(StrictArgs):
    pass


def handle_run_verification(
    args: RunVerificationArgs,
    *,
    repo_root: Path,
    settings: Settings,
    store: StateStore,
    run_id: str,
    edited_py_files: list[Path],
    on_check: Callable[[VerificationCheck], None] | None = None,
) -> ToolResult:
    pipeline = VerificationPipeline(
        repo_root, settings.verify, edited_py_files=edited_py_files, on_check=on_check
    )
    checks = pipeline.run(scope=args.scope)
    for check in checks:
        store.insert_verification_check(
            run_id,
            check_name=check.name,
            status=check.status,
            command=check.command,
            duration_ms=check.duration_ms,
            evidence=check.evidence,
        )
    ok = not any(c.status in {"fail", "flaky"} for c in checks)
    body = "\n".join(f"{c.name}:{c.status}" for c in checks)
    return ToolResult(ok=ok, summary="verification", content=body, truncated=False)


def handle_run_tests(
    _args: RunTestsArgs,
    *,
    repo_root: Path,
    settings: Settings,
    store: StateStore,
    run_id: str,
    edited_py_files: list[Path],
    on_check: Callable[[VerificationCheck], None] | None = None,
) -> ToolResult:
    return handle_run_verification(
        RunVerificationArgs(scope="test"),
        repo_root=repo_root,
        settings=settings,
        store=store,
        run_id=run_id,
        edited_py_files=edited_py_files,
        on_check=on_check,
    )
