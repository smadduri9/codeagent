"""run_command and bash tool handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import Field

from codeagent.config import ToolSettings
from codeagent.isolation.docker import execute_argv
from codeagent.tools.base import StrictArgs, ToolResult
from codeagent.tools.command_exec import DEFAULT_TIMEOUT_S
from codeagent.tools.paths import WorkspacePathError, resolve_workspace_path


class RunCommandArgs(StrictArgs):
    argv: list[str]
    cwd: str | None = None
    timeout_s: float = Field(default=DEFAULT_TIMEOUT_S, gt=0)
    env: dict[str, str] | None = None


class BashArgs(StrictArgs):
    command: str
    timeout_s: float = Field(default=DEFAULT_TIMEOUT_S, gt=0)


@dataclass
class CommandToolContext:
    workspace: Path
    settings: ToolSettings
    isolation_mode: str = "worktree"
    warn: Callable[[str], None] | None = field(default=None, repr=False)


def _resolve_cwd(ctx: CommandToolContext, cwd: str | None) -> Path:
    if cwd is None or cwd == ".":
        return ctx.workspace
    return resolve_workspace_path(ctx.workspace, cwd)


def handle_run_command(ctx: CommandToolContext, args: RunCommandArgs) -> ToolResult:
    if not args.argv:
        return ToolResult(
            ok=False,
            summary="run_command failed",
            content="argv must not be empty",
            truncated=False,
        )
    try:
        run_cwd = _resolve_cwd(ctx, args.cwd)
    except WorkspacePathError as exc:
        return ToolResult(ok=False, summary="run_command failed", content=str(exc), truncated=False)
    result = execute_argv(
        [str(part) for part in args.argv],
        cwd=run_cwd,
        timeout_s=args.timeout_s,
        env=args.env,
        max_output_chars=ctx.settings.max_output_chars,
        isolation_mode=ctx.isolation_mode,
        warn=ctx.warn,
    )
    summary = "run_command"
    if result.timed_out:
        summary = "run_command timed out"
    elif result.exit_code not in (0, None):
        summary = f"run_command exit {result.exit_code}"
    return ToolResult(
        ok=result.ok,
        summary=summary,
        content=result.combined_output,
        truncated=result.truncated,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )


def handle_bash(ctx: CommandToolContext, args: BashArgs) -> ToolResult:
    command = args.command.strip()
    if not command:
        return ToolResult(
            ok=False,
            summary="bash failed",
            content="command must not be empty",
            truncated=False,
        )
    result = execute_argv(
        ["/bin/bash", "-lc", command],
        cwd=ctx.workspace,
        timeout_s=args.timeout_s,
        env=None,
        max_output_chars=ctx.settings.max_output_chars,
        isolation_mode=ctx.isolation_mode,
        warn=ctx.warn,
    )
    summary = "bash"
    if result.timed_out:
        summary = "bash timed out"
    elif result.exit_code not in (0, None):
        summary = f"bash exit {result.exit_code}"
    return ToolResult(
        ok=result.ok,
        summary=summary,
        content=result.combined_output,
        truncated=result.truncated,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )
