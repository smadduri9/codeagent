"""Security: approvals, malformed args, decision ordering."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.loop import run_agent_loop
from codeagent.loop.policy import PolicyGate
from codeagent.permissions import ApprovalPrompt, PermissionRun
from codeagent.providers.base import Stop, StopReason, ToolCall, ToolCallEnd, ToolCallStart
from codeagent.providers.fake import FakeProvider
from codeagent.tools.registry import ToolRegistry


def test_malformed_tool_args_do_not_execute(tmp_path: Path) -> None:
    registry = ToolRegistry()
    run = PermissionRun(workspace=tmp_path, settings=Settings())
    gate = PolicyGate(run=run, registry=registry)
    call = ToolCall(id="c1", name="echo", args={"not_message": 1})
    decision, _ = gate.evaluate(call)
    assert gate.executed_calls == []
    from codeagent.permissions.types import Deny

    assert isinstance(decision, Deny)


def test_no_tool_runs_before_decision_recorded(tmp_path: Path) -> None:
    registry = ToolRegistry()
    run = PermissionRun(workspace=tmp_path, settings=Settings())
    gate = PolicyGate(run=run, registry=registry)
    order: list[str] = []

    def on_record(_record: object) -> None:
        order.append("record")

    gate.on_record = on_record
    original_execute = gate.execute_allowed

    def tracked(call: ToolCall, decision: object):
        order.append("execute")
        return original_execute(call, decision)

    gate.execute_allowed = tracked  # type: ignore[method-assign]

    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="echo"),
                ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "x"})),
                Stop(reason=StopReason.TOOL_CALLS),
            ],
            [Stop(reason=StopReason.STOP)],
        ],
    )
    run_agent_loop("g", provider, registry, max_iterations=2, policy=gate)
    assert order.index("record") < order.index("execute")


def test_approval_cannot_be_reused(tmp_path: Path) -> None:
    from codeagent.permissions import ApprovalStore, Ask, resolve_ask
    from codeagent.permissions.types import RiskLevel

    call = ToolCall(id="1", name="bash", args={"command": "rm a"})
    ask = Ask("rm", risk_level=RiskLevel.DESTRUCTIVE)
    store = ApprovalStore()
    prompt = ApprovalPrompt(choice="once")
    resolve_ask(call, ask, prompt=prompt, store=store, session_allowed_hashes=set())
    again = resolve_ask(call, ask, prompt=prompt, store=store, session_allowed_hashes=set())
    from codeagent.permissions import Deny

    assert isinstance(again, Deny)
