"""Path, secret, and tool risk rules (pure functions)."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import TYPE_CHECKING

from codeagent.config import PermissionSettings
from codeagent.permissions.types import (
    Allow,
    Ask,
    Decision,
    Deny,
    RiskLevel,
    strictest,
)
from codeagent.tools.paths import WorkspacePathError, resolve_workspace_path

if TYPE_CHECKING:
    from pydantic import BaseModel

_SECRET_GLOBS = (".env", ".env.*", "*.pem", "id_rsa*", "*credentials*")
_PROTECTED_WRITE_PARTS = frozenset({".git", ".codeagent"})


def default_tool_risk(tool_name: str) -> RiskLevel:
    mapping: dict[str, RiskLevel] = {
        "read_file": RiskLevel.READ_ONLY,
        "list_dir": RiskLevel.READ_ONLY,
        "glob": RiskLevel.READ_ONLY,
        "grep": RiskLevel.READ_ONLY,
        "write_file": RiskLevel.LOCAL_MUTATION,
        "edit_file": RiskLevel.LOCAL_MUTATION,
        "move_path": RiskLevel.DESTRUCTIVE,
        "delete_path": RiskLevel.DESTRUCTIVE,
        "run_command": RiskLevel.EXTERNAL_SIDE_EFFECT,
        "bash": RiskLevel.EXTERNAL_SIDE_EFFECT,
        "git_status": RiskLevel.READ_ONLY,
        "git_diff": RiskLevel.READ_ONLY,
        "git_log": RiskLevel.READ_ONLY,
        "git_show": RiskLevel.READ_ONLY,
        "web_fetch": RiskLevel.EXTERNAL_SIDE_EFFECT,
        "echo": RiskLevel.READ_ONLY,
    }
    return mapping.get(tool_name, RiskLevel.EXTERNAL_SIDE_EFFECT)


def risk_to_decision(
    level: RiskLevel,
    *,
    edit_mode: str,
    tool_name: str,
) -> Decision:
    if level is RiskLevel.FORBIDDEN:
        return Deny("forbidden", risk_level=level)
    if level is RiskLevel.DESTRUCTIVE:
        if tool_name == "delete_path":
            return Ask("deletion requires approval", risk_level=level)
        return Ask("destructive action", risk_level=level)
    if level is RiskLevel.EXTERNAL_SIDE_EFFECT:
        return Ask("external side effect", risk_level=level)
    if level is RiskLevel.LOCAL_MUTATION:
        if edit_mode == "ask":
            return Ask("edit_mode is ask", risk_level=level)
        return Allow(risk_level=level)
    return Allow(risk_level=level)


def _path_parts(path: Path) -> tuple[str, ...]:
    return path.parts


def is_protected_write_path(resolved: Path, workspace: Path) -> bool:
    root = workspace.resolve()
    try:
        rel = resolved.resolve().relative_to(root)
    except ValueError:
        return True
    return any(part in _PROTECTED_WRITE_PARTS for part in rel.parts)


def matches_secret_pattern(rel_path: str, patterns: tuple[str, ...]) -> bool:
    name = Path(rel_path).name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def secret_patterns(settings: PermissionSettings) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*_SECRET_GLOBS, *settings.secret_paths)))


def path_read_decision(
    workspace: Path,
    raw_path: str,
    settings: PermissionSettings,
) -> Decision:
    try:
        resolved = resolve_workspace_path(workspace, raw_path)
    except WorkspacePathError:
        return Deny("path escapes workspace", risk_level=RiskLevel.FORBIDDEN)
    root = workspace.resolve()
    rel = str(resolved.relative_to(root)) if resolved != root else "."
    if matches_secret_pattern(rel, secret_patterns(settings)):
        return Ask("secret path read", risk_level=RiskLevel.READ_ONLY)
    return Allow(risk_level=RiskLevel.READ_ONLY)


def path_write_decision(
    workspace: Path,
    raw_path: str,
    settings: PermissionSettings,
) -> Decision:
    try:
        resolved = resolve_workspace_path(workspace, raw_path)
    except WorkspacePathError:
        return Deny("path escapes workspace", risk_level=RiskLevel.FORBIDDEN)
    if is_protected_write_path(resolved, workspace):
        return Deny("protected path", risk_level=RiskLevel.FORBIDDEN)
    root = workspace.resolve()
    rel = str(resolved.relative_to(root)) if resolved != root else "."
    if matches_secret_pattern(rel, secret_patterns(settings)):
        return Deny("secret path write", risk_level=RiskLevel.FORBIDDEN)
    return Allow(risk_level=RiskLevel.LOCAL_MUTATION)


def extract_redirect_paths(segment: str) -> list[str]:
    """Return redirect target paths from a shell segment."""
    paths: list[str] = []
    tokens = re.split(r"\s+", segment.strip())
    i = 0
    while i < len(tokens):
        piece = tokens[i]
        if piece in {">", ">>", "1>", "2>", "1>>", "2>>"} and i + 1 < len(tokens):
            paths.append(tokens[i + 1].strip("'\"`"))
            i += 2
            continue
        if re.match(r"^\d+>>?$", piece) and i + 1 < len(tokens):
            paths.append(tokens[i + 1].strip("'\"`"))
            i += 2
            continue
        if piece.startswith(">") and len(piece) > 1:
            paths.append(piece[1:].strip("'\"`"))
        i += 1
    return paths


def file_tool_path_decisions(
    tool_name: str,
    args: dict[str, object] | BaseModel,
    workspace: Path,
    settings: PermissionSettings,
) -> list[Decision]:
    raw = args if isinstance(args, dict) else args.model_dump()
    decisions: list[Decision] = []
    path_keys = {
        "read_file": ("path", "read"),
        "list_dir": ("path", "read"),
        "glob": ("pattern", "read"),
        "grep": ("path", "read"),
        "write_file": ("path", "write"),
        "edit_file": ("path", "write"),
        "move_path": ("src", "read"),
        "delete_path": ("path", "write"),
    }
    spec = path_keys.get(tool_name)
    if spec is None:
        return decisions
    key, mode = spec
    value = raw.get(key)
    if isinstance(value, str) and value:
        if mode == "read":
            decisions.append(path_read_decision(workspace, value, settings))
        else:
            decisions.append(path_write_decision(workspace, value, settings))
    if tool_name == "move_path":
        dst = raw.get("dst")
        if isinstance(dst, str) and dst:
            decisions.append(path_write_decision(workspace, dst, settings))
    return decisions


def combine_tool_decision(
    tool_name: str,
    settings: PermissionSettings,
    path_decisions: list[Decision],
) -> Decision:
    base = risk_to_decision(
        default_tool_risk(tool_name),
        edit_mode=settings.edit_mode,
        tool_name=tool_name,
    )
    return strictest(base, *path_decisions)
