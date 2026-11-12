"""The interactive approval prompt shows what is being approved."""

from __future__ import annotations

import io

import pytest
import typer
from rich.console import Console

from codeagent.permissions.types import Allow, Ask, Deny, RiskLevel
from codeagent.providers.base import ToolCall
from codeagent.runtime.approvals import CliApprovalPrompt

_XFAIL = pytest.mark.xfail(strict=True, reason="FIX-02")


def _resolve(
    monkeypatch: pytest.MonkeyPatch, call: ToolCall, answer: str = "n"
) -> tuple[str, object]:
    monkeypatch.setattr(typer, "prompt", lambda *_a, **_k: answer)
    buffer = io.StringIO()
    prompt = CliApprovalPrompt(console=Console(file=buffer, width=200, color_system=None))
    ask = Ask("unknown command", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    decision = prompt.resolve(call, ask)
    return buffer.getvalue(), decision


@_XFAIL
@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("bash", {"command": "pytest -q tests/unit"}, "pytest -q tests/unit"),
        ("run_command", {"argv": ["npm", "install", "left-pad"]}, '"left-pad"'),
        ("delete_path", {"path": "src/old.py", "recursive": True}, "src/old.py"),
    ],
)
def test_prompt_shows_arguments(
    monkeypatch: pytest.MonkeyPatch, name: str, args: dict[str, object], expected: str
) -> None:
    output, _ = _resolve(monkeypatch, ToolCall(id="1", name=name, args=args))
    assert expected in output
    assert name in output


@_XFAIL
def test_prompt_truncates_long_values(monkeypatch: pytest.MonkeyPatch) -> None:
    call = ToolCall(id="1", name="bash", args={"command": "echo " + "x" * 5000})
    output, _ = _resolve(monkeypatch, call)
    assert "echo xxxx" in output
    assert "chars total" in output
    assert len(output) < 2000


@_XFAIL
def test_prompt_escapes_markup_and_control_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    call = ToolCall(id="1", name="bash", args={"command": "echo [red]hi[/red] \x1b[2J"})
    output, _ = _resolve(monkeypatch, call)
    assert "[red]hi[/red]" in output
    assert "\x1b" not in output


def test_prompt_answers_still_map_to_decisions(monkeypatch: pytest.MonkeyPatch) -> None:
    call = ToolCall(id="1", name="bash", args={"command": "ls"})
    _, denied = _resolve(monkeypatch, call, "n")
    _, once = _resolve(monkeypatch, call, "y")
    _, session = _resolve(monkeypatch, call, "s")
    assert isinstance(denied, Deny)
    assert isinstance(once, Allow)
    assert isinstance(session, Allow)
