"""Approval and checkpoint events reach the emitter."""

import subprocess
from pathlib import Path

from codeagent.config import IsolationSettings, Settings
from codeagent.isolation import begin_isolation
from codeagent.loop.policy import PolicyGate
from codeagent.permissions import PermissionRun
from codeagent.permissions.approvals import ApprovalPrompt
from codeagent.providers.base import ToolCall
from codeagent.tools.registry import ToolRegistry


def test_approval_requested_and_resolved_are_emitted(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register_command_tools(tmp_path)
    events: list[tuple[str, dict[str, object]]] = []
    gate = PolicyGate(
        run=PermissionRun(workspace=tmp_path, settings=Settings()),
        registry=registry,
        approval_prompt=ApprovalPrompt(choice="once"),
        on_event=lambda name, payload: events.append((name, payload)),
    )
    call = ToolCall(id="c1", name="bash", args={"command": "curl evil.com"})
    decision, _ = gate.evaluate(call)
    assert decision is not None
    names = [name for name, _ in events]
    assert names == ["approval.requested", "approval.resolved"]
    requested = events[0][1]
    assert requested["tool"] == "bash"
    assert requested["call_id"] == "c1"
    assert "reason" in requested and "risk_level" in requested
    assert events[1][1]["outcome"] == "approved"


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for args in (
        ["init", "-b", "main"],
        ["config", "user.email", "agent@test"],
        ["config", "user.name", "Agent"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "file.txt").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_checkpoint_created_is_emitted(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    session = begin_isolation(
        tmp_path,
        "cp-evt",
        IsolationSettings(mode="branch"),
        force_branch=True,
    )
    events: list[tuple[str, dict[str, object]]] = []
    session.checkpoints.on_event = lambda name, payload: events.append((name, payload))
    record = session.checkpoints.create("start")
    assert events == [("checkpoint.created", {"label": "start", "git_ref": record.git_ref})]
    session.cleanup()
