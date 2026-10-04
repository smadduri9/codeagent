"""Read-only git tools backed by the typed git wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from codeagent.config import ToolSettings
from codeagent.isolation.git_wrapper import run_git
from codeagent.tools.base import StrictArgs, ToolResult
from codeagent.tools.truncate import truncate_content


class GitStatusArgs(StrictArgs):
    pass


class GitDiffArgs(StrictArgs):
    path: str | None = None
    staged: bool = False


class GitLogArgs(StrictArgs):
    max_count: int = Field(default=10, ge=1, le=500)


class GitShowArgs(StrictArgs):
    ref: str = "HEAD"


@dataclass
class GitToolContext:
    repo: Path
    settings: ToolSettings


def _cap(ctx: GitToolContext, body: str) -> tuple[str, bool]:
    return truncate_content(body, ctx.settings.max_output_chars, keep="tail")


def handle_git_status(ctx: GitToolContext, _args: GitStatusArgs) -> ToolResult:
    try:
        result = run_git(ctx.repo, ["status", "--short", "--branch"], check=False)
    except OSError as exc:
        return ToolResult(ok=False, summary="git_status failed", content=str(exc), truncated=False)
    body = (result.stdout + result.stderr).strip()
    capped, truncated = _cap(ctx, body + ("\n" if body else ""))
    ok = result.returncode == 0
    return ToolResult(
        ok=ok,
        summary="git status",
        content=capped,
        truncated=truncated,
        exit_code=result.returncode,
    )


def handle_git_diff(ctx: GitToolContext, args: GitDiffArgs) -> ToolResult:
    command = ["diff"]
    if args.staged:
        command.append("--cached")
    if args.path:
        command.extend(["--", args.path])
    try:
        result = run_git(ctx.repo, command, check=False)
    except OSError as exc:
        return ToolResult(ok=False, summary="git_diff failed", content=str(exc), truncated=False)
    body = result.stdout
    capped, truncated = _cap(ctx, body)
    ok = result.returncode in (0, 1)
    return ToolResult(
        ok=ok,
        summary="git diff",
        content=capped,
        truncated=truncated,
        exit_code=result.returncode,
    )


def handle_git_log(ctx: GitToolContext, args: GitLogArgs) -> ToolResult:
    try:
        result = run_git(
            ctx.repo,
            ["log", f"-{args.max_count}", "--oneline", "--decorate"],
            check=False,
        )
    except OSError as exc:
        return ToolResult(ok=False, summary="git_log failed", content=str(exc), truncated=False)
    if result.returncode != 0 and "does not have any commits yet" in result.stderr:
        capped, truncated = _cap(ctx, "")
        return ToolResult(
            ok=True,
            summary="git log (no commits)",
            content=capped,
            truncated=truncated,
            exit_code=0,
        )
    body = result.stdout
    capped, truncated = _cap(ctx, body)
    ok = result.returncode == 0
    return ToolResult(
        ok=ok,
        summary="git log",
        content=capped,
        truncated=truncated,
        exit_code=result.returncode,
    )


def handle_git_show(ctx: GitToolContext, args: GitShowArgs) -> ToolResult:
    try:
        result = run_git(ctx.repo, ["show", "--stat", "--patch", args.ref], check=False)
    except OSError as exc:
        return ToolResult(ok=False, summary="git_show failed", content=str(exc), truncated=False)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        return ToolResult(
            ok=False,
            summary="git_show failed",
            content=message,
            truncated=False,
            exit_code=result.returncode,
        )
    body = result.stdout
    capped, truncated = _cap(ctx, body)
    return ToolResult(
        ok=True,
        summary="git show",
        content=capped,
        truncated=truncated,
        exit_code=0,
    )
