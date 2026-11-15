"""Plan and verification tools have an explicit risk level; unknown tools still ask."""

from __future__ import annotations

from pathlib import Path

import pytest

from codeagent.config import PermissionSettings, Settings
from codeagent.permissions import Allow, Ask, PermissionRun, decide
from codeagent.permissions.rules import default_tool_risk
from codeagent.permissions.types import RiskLevel
from codeagent.providers.base import ToolCall

_CASES: list[tuple[str, dict[str, object], RiskLevel]] = [
    ("update_plan", {"items": [{"text": "step", "status": "pending"}]}, RiskLevel.READ_ONLY),
    ("run_tests", {}, RiskLevel.LOCAL_MUTATION),
    ("run_verification", {}, RiskLevel.LOCAL_MUTATION),
    ("run_verification", {"scope": "lint"}, RiskLevel.LOCAL_MUTATION),
]


def _decide(name: str, args: dict[str, object], tmp_path: Path, settings: Settings) -> object:
    run = PermissionRun(workspace=tmp_path, settings=settings)
    return decide(ToolCall(id="1", name=name, args=args), args, run)


@pytest.mark.parametrize(("name", "args", "level"), _CASES)
def test_workflow_tools_are_allowed_by_rule(
    name: str, args: dict[str, object], level: RiskLevel, tmp_path: Path
) -> None:
    decision = _decide(name, args, tmp_path, Settings())
    assert isinstance(decision, Allow)
    assert decision.decided_by == "rule"
    assert default_tool_risk(name) is level


@pytest.mark.parametrize("name", ["run_tests", "run_verification"])
def test_verification_tools_ask_when_edit_mode_is_ask(name: str, tmp_path: Path) -> None:
    settings = Settings(permissions=PermissionSettings(edit_mode="ask"))
    decision = _decide(name, {}, tmp_path, settings)
    assert isinstance(decision, Ask)
    assert decision.risk_level is RiskLevel.LOCAL_MUTATION


def test_update_plan_never_asks(tmp_path: Path) -> None:
    settings = Settings(permissions=PermissionSettings(edit_mode="ask"))
    assert isinstance(_decide("update_plan", {"items": []}, tmp_path, settings), Allow)


@pytest.mark.parametrize("name", ["not_a_tool", "run_test", "update_plans", "web_fetch", ""])
def test_unknown_tools_still_ask(name: str, tmp_path: Path) -> None:
    decision = _decide(name, {}, tmp_path, Settings())
    assert isinstance(decision, Ask)
    assert default_tool_risk(name) is RiskLevel.EXTERNAL_SIDE_EFFECT
