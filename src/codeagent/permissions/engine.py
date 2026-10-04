"""Permission engine: pure ``decide`` for tool calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeagent.permissions.rules import (
    combine_tool_decision,
    file_tool_path_decisions,
)
from codeagent.permissions.run_context import PermissionRun
from codeagent.permissions.shell_classify import classify_argv, classify_shell
from codeagent.permissions.types import Ask, Decision, strictest
from codeagent.providers.base import ToolCall

if TYPE_CHECKING:
    from pydantic import BaseModel


def decide(
    call: ToolCall,
    args: dict[str, object] | BaseModel,
    run: PermissionRun,
) -> Decision:
    """Return allow, ask, or deny for a validated tool call (no chat history)."""
    settings = run.permissions
    workspace = run.workspace

    path_decisions = file_tool_path_decisions(call.name, args, workspace, settings)
    if call.name == "bash":
        raw = args if isinstance(args, dict) else args.model_dump()
        command = raw.get("command")
        if not isinstance(command, str) or not command.strip():
            return Ask("empty bash command")
        shell_decision = classify_shell(command, workspace, settings)
        base = combine_tool_decision(call.name, settings, path_decisions)
        return strictest(base, shell_decision)

    if call.name == "run_command":
        raw = args if isinstance(args, dict) else args.model_dump()
        argv = raw.get("argv")
        if not isinstance(argv, list):
            return Ask("run_command requires argv")
        str_argv = [str(part) for part in argv]
        argv_decision = classify_argv(str_argv, settings)
        base = combine_tool_decision(call.name, settings, path_decisions)
        return strictest(base, argv_decision)

    return combine_tool_decision(call.name, settings, path_decisions)
