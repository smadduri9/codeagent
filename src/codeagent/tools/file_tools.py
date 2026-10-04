"""Handlers for workspace file and search tools."""

from __future__ import annotations

import ast
import difflib
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from codeagent.tools.base import StrictArgs, ToolResult
from codeagent.tools.gitignore import is_ignored, load_gitignore_patterns
from codeagent.tools.paths import WorkspacePathError, resolve_workspace_path
from codeagent.tools.truncate import truncate_content
from codeagent.tools.workspace_context import FileChangedEvent, WorkspaceToolContext

READ_FILE_MAX_BYTES = 1_048_576
GLOB_MAX_RESULTS = 200
GREP_MAX_MATCHES = 500
BINARY_SAMPLE_BYTES = 8192


class ReadFileArgs(StrictArgs):
    path: str
    offset: int = Field(default=1, ge=1)
    limit: int | None = Field(default=None, ge=1)


class ListDirArgs(StrictArgs):
    path: str = "."


class GlobArgs(StrictArgs):
    pattern: str


class GrepArgs(StrictArgs):
    pattern: str
    path: str | None = None
    glob: str | None = None
    context: int = Field(default=0, ge=0)
    output_mode: str = "lines"


class WriteFileArgs(StrictArgs):
    path: str
    content: str


class EditFileArgs(StrictArgs):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class MovePathArgs(StrictArgs):
    src: str
    dst: str


class DeletePathArgs(StrictArgs):
    path: str
    recursive: bool = False


def _fail(summary: str, message: str) -> ToolResult:
    return ToolResult(ok=False, summary=summary, content=message, truncated=False)


def _ok(summary: str, content: str, *, truncated: bool = False) -> ToolResult:
    return ToolResult(ok=True, summary=summary, content=content, truncated=truncated)


def _cap_output(ctx: WorkspaceToolContext, content: str) -> tuple[str, bool]:
    return truncate_content(content, ctx.settings.max_output_chars, keep="tail")


def _is_binary_file(path: Path) -> bool:
    with path.open("rb") as stream:
        chunk = stream.read(BINARY_SAMPLE_BYTES)
    return b"\x00" in chunk


def _format_line_numbered(lines: list[str], start_line: int) -> str:
    width = max(len(str(start_line + len(lines) - 1)), 1)
    parts: list[str] = []
    for index, line in enumerate(lines):
        number = start_line + index
        parts.append(f"{number:>{width}}|{line}")
    return "\n".join(parts) + ("\n" if lines else "")


def _find_match_lines(content: str, needle: str) -> list[int]:
    lines = content.splitlines(keepends=True)
    joined = "".join(lines)
    if not needle:
        return []
    positions: list[int] = []
    start = 0
    while True:
        index = joined.find(needle, start)
        if index == -1:
            break
        line_no = joined.count("\n", 0, index) + 1
        positions.append(line_no)
        start = index + max(len(needle), 1)
    return positions


def _parse_check(path: Path, content: str) -> str | None:
    if path.suffix == ".py":
        try:
            ast.parse(content)
        except SyntaxError as exc:
            return f"Python syntax error after edit: {exc.msg} (line {exc.lineno})"
    return None


def _record_edit(
    ctx: WorkspaceToolContext,
    path: Path,
    before: str,
    after: str,
) -> None:
    rel = path.relative_to(ctx.workspace.resolve()).as_posix()
    diff_lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
    )
    diff = "".join(diff_lines)
    ctx.file_changed_events.append(FileChangedEvent(path=rel, diff=diff))
    ctx.read_tracker.record(path, after)


def _resolve(ctx: WorkspaceToolContext, raw: str) -> Path | ToolResult:
    try:
        return resolve_workspace_path(ctx.workspace, raw)
    except WorkspacePathError as exc:
        return _fail("path resolution failed", exc.message)


def handle_read_file(ctx: WorkspaceToolContext, args: ReadFileArgs) -> ToolResult:
    resolved = _resolve(ctx, args.path)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_file():
        return _fail("read_file failed", "not a file")
    size = resolved.stat().st_size
    if size > READ_FILE_MAX_BYTES:
        return _fail(
            "read_file failed",
            f"file exceeds size cap ({size} bytes; max {READ_FILE_MAX_BYTES})",
        )
    if _is_binary_file(resolved):
        return _fail("read_file failed", "binary file")
    text = resolved.read_text(encoding="utf-8")
    all_lines = text.splitlines()
    start = args.offset
    if start > len(all_lines) and all_lines:
        return _ok("read_file", "")
    limit = args.limit if args.limit is not None else ctx.settings.read_default_lines
    slice_lines = all_lines[start - 1 : start - 1 + limit]
    body = _format_line_numbered(slice_lines, start)
    ctx.read_tracker.record(resolved, text)
    capped, truncated = _cap_output(ctx, body)
    summary = f"read {len(slice_lines)} lines from {args.path}"
    return _ok(summary, capped, truncated=truncated)


def handle_list_dir(ctx: WorkspaceToolContext, args: ListDirArgs) -> ToolResult:
    resolved = _resolve(ctx, args.path)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_dir():
        return _fail("list_dir failed", "not a directory")
    patterns = load_gitignore_patterns(ctx.workspace.resolve())
    root = ctx.workspace.resolve()
    entries: list[str] = []
    for child in sorted(resolved.iterdir(), key=lambda p: p.name.lower()):
        rel = child.relative_to(root)
        if is_ignored(rel, patterns):
            continue
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{rel.as_posix()}{suffix}")
    body = "\n".join(entries) + ("\n" if entries else "")
    capped, truncated = _cap_output(ctx, body)
    return _ok(f"listed {len(entries)} entries", capped, truncated=truncated)


def _rg_path() -> str | None:
    return shutil.which("rg")


def handle_glob(ctx: WorkspaceToolContext, args: GlobArgs) -> ToolResult:
    rg = _rg_path()
    if rg is None:
        return _fail("glob failed", "ripgrep (rg) is not installed or not on PATH")
    start = time.perf_counter()
    command = [rg, "--files", "-g", args.pattern, "--sort", "modified"]
    completed = subprocess.run(
        command,
        cwd=ctx.workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    if completed.returncode not in (0, 1):
        message = completed.stderr.strip() or "rg failed"
        return ToolResult(
            ok=False,
            summary="glob failed",
            content=message,
            truncated=False,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
    paths = [line for line in completed.stdout.splitlines() if line]
    truncated_list = len(paths) > GLOB_MAX_RESULTS
    if truncated_list:
        paths = paths[:GLOB_MAX_RESULTS]
    body = "\n".join(paths) + ("\n" if paths else "")
    if truncated_list:
        body += f"\n[truncated: {GLOB_MAX_RESULTS} results shown; narrow the pattern]"
    capped, truncated = _cap_output(ctx, body)
    return ToolResult(
        ok=True,
        summary=f"glob {len(paths)} paths",
        content=capped,
        truncated=truncated,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
    )


def _grep_command(args: GrepArgs, rg: str) -> list[str]:
    command = [rg, "--no-heading", "--color=never"]
    if args.output_mode == "files":
        command.append("--files-with-matches")
    elif args.output_mode == "count":
        command.append("--count-matches")
    if args.context > 0 and args.output_mode == "lines":
        command.extend(["-C", str(args.context)])
    if args.glob:
        command.extend(["-g", args.glob])
    command.append(args.pattern)
    if args.path:
        command.append(args.path)
    return command


def handle_grep(ctx: WorkspaceToolContext, args: GrepArgs) -> ToolResult:
    if args.output_mode not in {"files", "lines", "count"}:
        return _fail("grep failed", "output_mode must be files, lines, or count")
    rg = _rg_path()
    if rg is None:
        return _fail("grep failed", "ripgrep (rg) is not installed or not on PATH")
    if args.path:
        resolved = _resolve(ctx, args.path)
        if isinstance(resolved, ToolResult):
            return resolved
    start = time.perf_counter()
    command = _grep_command(args, rg)
    completed = subprocess.run(
        command,
        cwd=ctx.workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    if completed.returncode not in (0, 1):
        message = completed.stderr.strip() or "rg failed"
        return ToolResult(
            ok=False,
            summary="grep failed",
            content=message,
            truncated=False,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
    lines = completed.stdout.splitlines()
    if len(lines) > GREP_MAX_MATCHES:
        lines = lines[:GREP_MAX_MATCHES]
        body = "\n".join(lines) + f"\n[truncated: showing first {GREP_MAX_MATCHES} matches]"
    else:
        body = "\n".join(lines) + ("\n" if lines else "")
    capped, truncated = _cap_output(ctx, body)
    return ToolResult(
        ok=True,
        summary=f"grep ({args.output_mode})",
        content=capped,
        truncated=truncated,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
    )


def handle_write_file(ctx: WorkspaceToolContext, args: WriteFileArgs) -> ToolResult:
    resolved = _resolve(ctx, args.path)
    if isinstance(resolved, ToolResult):
        return resolved
    if resolved.exists():
        return _fail("write_file failed", "file already exists")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(args.content, encoding="utf-8")
    _record_edit(ctx, resolved, "", args.content)
    return _ok("write_file", f"created {args.path}")


def handle_edit_file(ctx: WorkspaceToolContext, args: EditFileArgs) -> ToolResult:
    resolved = _resolve(ctx, args.path)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.is_file():
        return _fail("edit_file failed", "not a file")
    before = resolved.read_text(encoding="utf-8")
    stale = ctx.read_tracker.check_stale(resolved, before)
    if stale is not None:
        return _fail("edit_file failed", stale)
    if args.old_string not in before:
        return _fail(
            "edit_file failed",
            "old_string not found (0 matches)",
        )
    matches = _find_match_lines(before, args.old_string)
    if not args.replace_all and len(matches) != 1:
        lines = ", ".join(str(n) for n in matches)
        return _fail(
            "edit_file failed",
            f"old_string is not unique ({len(matches)} matches at lines {lines})",
        )
    if args.replace_all:
        after = before.replace(args.old_string, args.new_string)
    else:
        after = before.replace(args.old_string, args.new_string, 1)
    parse_error = _parse_check(resolved, after)
    resolved.write_text(after, encoding="utf-8")
    _record_edit(ctx, resolved, before, after)
    parts = [f"edited {args.path}"]
    if parse_error:
        parts.append(parse_error)
    return _ok("edit_file", "; ".join(parts))


def handle_move_path(ctx: WorkspaceToolContext, args: MovePathArgs) -> ToolResult:
    src = _resolve(ctx, args.src)
    if isinstance(src, ToolResult):
        return src
    dst = _resolve(ctx, args.dst)
    if isinstance(dst, ToolResult):
        return dst
    if not src.exists():
        return _fail("move_path failed", "source does not exist")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return _fail("move_path failed", "destination already exists")
    shutil.move(str(src), str(dst))
    return _ok("move_path", f"moved {args.src} -> {args.dst}")


def handle_delete_path(ctx: WorkspaceToolContext, args: DeletePathArgs) -> ToolResult:
    resolved = _resolve(ctx, args.path)
    if isinstance(resolved, ToolResult):
        return resolved
    if not resolved.exists():
        return _fail("delete_path failed", "path does not exist")
    if resolved.is_dir():
        if args.recursive:
            shutil.rmtree(resolved)
        else:
            try:
                resolved.rmdir()
            except OSError:
                return _fail("delete_path failed", "directory not empty (use recursive=true)")
    else:
        os.remove(resolved)
    return _ok("delete_path", f"deleted {args.path}")


def _bind[ArgModel: BaseModel](
    ctx: WorkspaceToolContext,
    handler: Callable[[WorkspaceToolContext, ArgModel], ToolResult],
) -> Callable[[ArgModel], ToolResult]:
    def wrapped(args: ArgModel) -> ToolResult:
        return handler(ctx, args)

    return wrapped
