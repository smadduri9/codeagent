"""Bootstrap tools, policy, and prompts for live CLI runs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from codeagent.config import Settings
from codeagent.context.instructions import load_instructions
from codeagent.context.prompts import load_system_prompt
from codeagent.loop.policy import PolicyGate
from codeagent.permissions.approvals import ApprovalPrompt, ApprovalResponder
from codeagent.permissions.run_context import PermissionRun
from codeagent.runtime.approvals import CliApprovalPrompt
from codeagent.state.store import StateStore
from codeagent.tools.command_tools import CommandToolContext
from codeagent.tools.registry import ToolRegistry


def build_system_prompt(repo_root: Path, settings: Settings) -> str:
    system = load_system_prompt()
    loaded = load_instructions(
        repo_root,
        max_tokens=settings.tools.instructions_max_tokens,
    )
    if loaded.text:
        system = f"{system}\n\n# Repository instructions\n\n{loaded.text}"
    return system


def build_tool_registry(
    *,
    workspace: Path,
    repo_root: Path,
    settings: Settings,
    store: StateStore | None,
    run_id: str | None,
    warn: Callable[[str], None],
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_filesystem_tools(workspace, settings.tools)
    registry.register_command_tools(
        workspace,
        settings.tools,
        context=CommandToolContext(
            workspace=workspace,
            settings=settings.tools,
            isolation_mode=settings.isolation.mode,
            warn=warn,
        ),
    )
    registry.register_git_tools(repo_root, settings.tools)
    if store is not None and run_id is not None:
        registry.register_workflow_tools(
            store=store,
            run_id=run_id,
            repo_root=repo_root,
            settings=settings,
            edited_py_files=[],
        )
    return registry


def build_policy_gate(
    *,
    workspace: Path,
    settings: Settings,
    registry: ToolRegistry,
    interactive: bool,
    scripted: bool,
) -> PolicyGate:
    prompt: ApprovalResponder | None
    if not interactive:
        prompt = None
    elif scripted:
        prompt = cast(ApprovalResponder, ApprovalPrompt(choice="once"))
    else:
        from rich.console import Console

        prompt = cast(ApprovalResponder, CliApprovalPrompt(console=Console(stderr=True)))
    perm = PermissionRun(workspace=workspace, settings=settings, interactive=interactive)
    return PolicyGate(run=perm, registry=registry, approval_prompt=prompt)
