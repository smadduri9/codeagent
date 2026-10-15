"""The completion gate must see edits and test runs on the policy path, not only the legacy one."""

from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.loop import run_agent_loop
from codeagent.loop.completion_gate import CompletionGate
from codeagent.loop.policy import PolicyGate
from codeagent.loop.runner import _is_pytest_command
from codeagent.permissions.approvals import ApprovalChoice
from codeagent.permissions.run_context import PermissionRun
from codeagent.permissions.types import Allow, Ask, Decision, RiskLevel
from codeagent.providers.base import (
    MessageRole,
    ModelEvent,
    Stop,
    StopReason,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
)
from codeagent.providers.fake import FakeProvider
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import StrictArgs, ToolRegistry


class _AllowAll:
    choice: ApprovalChoice = "session"

    def resolve(self, call: ToolCall, ask: Ask) -> Decision:
        return Allow(risk_level=ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT)


def _registry(workspace: Path, exit_code: int) -> ToolRegistry:
    class RunCommandArgs(StrictArgs):
        argv: list[str]

    registry = ToolRegistry()
    registry.register_filesystem_tools(workspace)
    registry.register(
        "run_command",
        "Run a command (test stub).",
        RunCommandArgs,
        lambda _a: ToolResult(
            ok=exit_code == 0,
            summary="run_command",
            content="1 passed" if exit_code == 0 else "1 failed",
            truncated=False,
            exit_code=exit_code,
        ),
        parameters={
            "type": "object",
            "properties": {"argv": {"type": "array", "items": {"type": "string"}}},
            "required": ["argv"],
            "additionalProperties": False,
        },
    )
    return registry


def _turn(call: ToolCall) -> list[ModelEvent]:
    return [
        ToolCallStart(id=call.id, name=call.name),
        ToolCallEnd(call=call),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


_EDIT = ToolCall(id="e1", name="write_file", args={"path": "fix.py", "content": "x = 1\n"})
_PYTEST = ToolCall(id="t1", name="run_command", args={"argv": ["python", "-m", "pytest", "-q"]})
_STOP: list[ModelEvent] = [Stop(reason=StopReason.STOP)]


def _run(tmp_path: Path, turns: list[list[ModelEvent]], exit_code: int = 0) -> tuple[str, int]:
    registry = _registry(tmp_path, exit_code)
    policy = PolicyGate(
        run=PermissionRun(workspace=tmp_path, settings=Settings(), interactive=True),
        registry=registry,
        approval_prompt=_AllowAll(),
    )
    result = run_agent_loop(
        "fix it", FakeProvider(turns), registry, max_iterations=8, policy=policy
    )
    prompts = sum(
        1
        for m in result.history
        if m.role is MessageRole.USER and m.content == CompletionGate.prompt_message()
    )
    return result.stop_reason, prompts


def test_edit_then_stop_prompts_for_verification(tmp_path: Path) -> None:
    stop_reason, prompts = _run(tmp_path, [_turn(_EDIT), _STOP, _STOP])
    assert (tmp_path / "fix.py").exists()
    assert prompts == 1
    assert stop_reason == "completed_unverified"


def test_passing_pytest_after_edit_completes(tmp_path: Path) -> None:
    stop_reason, prompts = _run(tmp_path, [_turn(_EDIT), _turn(_PYTEST), _STOP])
    assert prompts == 0
    assert stop_reason == StopReason.STOP.value


def test_failing_pytest_after_edit_still_prompts(tmp_path: Path) -> None:
    stop_reason, prompts = _run(tmp_path, [_turn(_EDIT), _turn(_PYTEST), _STOP, _STOP], exit_code=1)
    assert prompts == 1
    assert stop_reason == "completed_unverified"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["pytest", "-q"], True),
        (["/env/bin/pytest", "tests/test_x.py"], True),
        (["python", "-m", "pytest", "-x"], True),
        (["/env/bin/python3.12", "-m", "pytest"], True),
        (["python", "-c", "import pytest"], False),
        (["python", "repro.py"], False),
        (["pytest-watch"], False),
        ([], False),
    ],
)
def test_is_pytest_command(argv: list[str], expected: bool) -> None:
    assert _is_pytest_command(ToolCall(id="c", name="run_command", args={"argv": argv})) is expected


def test_is_pytest_command_ignores_other_tools() -> None:
    assert not _is_pytest_command(ToolCall(id="c", name="bash", args={"argv": ["pytest"]}))
