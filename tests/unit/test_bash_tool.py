"""bash tool classification and execution integration."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.loop import run_agent_loop
from codeagent.loop.policy import PolicyGate
from codeagent.permissions import Allow, PermissionRun, classify_shell, resolve_non_interactive
from codeagent.permissions.engine import decide
from codeagent.permissions.types import Ask, Deny
from codeagent.providers.base import (
    MessageRole,
    Stop,
    StopReason,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
)
from codeagent.providers.fake import FakeProvider
from codeagent.tools.registry import ToolRegistry


def _registry_with_bash(workspace: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_command_tools(workspace)
    return registry


def test_bash_allow_runs(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = _registry_with_bash(workspace)
    run = PermissionRun(workspace=workspace, settings=Settings())
    assert isinstance(classify_shell("pwd", workspace, run.permissions), Allow)
    call = ToolCall(id="1", name="bash", args={"command": "pwd"})
    result = registry.run(call)
    assert result.ok


def test_bash_ask_requires_approval_non_interactive(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    run = PermissionRun(workspace=workspace, settings=Settings(), interactive=False)
    call = ToolCall(id="1", name="bash", args={"command": "rm x"})
    decision = decide(call, call.args, run)
    assert isinstance(decision, Ask)
    resolved = resolve_non_interactive(decision, interactive=False)
    assert isinstance(resolved, Deny)


def test_bash_deny_never_runs(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    run = PermissionRun(workspace=workspace, settings=Settings())
    call = ToolCall(id="1", name="bash", args={"command": "sudo rm -rf /"})
    decision = decide(call, call.args, run)
    assert isinstance(decision, Deny)


def test_bash_redirect_outside_workspace_denied(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    run = PermissionRun(workspace=workspace, settings=Settings())
    call = ToolCall(id="1", name="bash", args={"command": f"echo hi > {outside}"})
    decision = decide(call, call.args, run)
    assert isinstance(decision, Deny)


def test_bash_loop_denies_rm_without_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = _registry_with_bash(workspace)
    run = PermissionRun(workspace=workspace, settings=Settings(), interactive=False)
    gate = PolicyGate(run=run, registry=registry)
    executed: list[str] = []

    def track(call: ToolCall, decision: object):
        executed.append(call.name)
        return gate.execute_allowed(call, decision)

    gate.execute_allowed = track  # type: ignore[method-assign]
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="bash"),
                ToolCallEnd(call=ToolCall(id="c1", name="bash", args={"command": "rm x"})),
                Stop(reason=StopReason.TOOL_CALLS),
            ],
            [Stop(reason=StopReason.STOP)],
        ],
    )
    result = run_agent_loop("t", provider, registry, max_iterations=3, policy=gate)
    assert executed == []
    tool_msgs = [m for m in result.history if m.role is MessageRole.TOOL]
    assert tool_msgs
