"""Approval binding and single-use behavior."""

from codeagent.permissions import ApprovalPrompt, ApprovalStore, Ask, Deny, resolve_ask
from codeagent.permissions.approvals import tool_call_hash
from codeagent.permissions.types import RiskLevel
from codeagent.providers.base import ToolCall


def test_approval_hash_changes_with_args() -> None:
    a = ToolCall(id="1", name="bash", args={"command": "rm a"})
    b = ToolCall(id="2", name="bash", args={"command": "rm b"})
    assert tool_call_hash(a) != tool_call_hash(b)


def test_single_use_approval_rejects_replay() -> None:
    call = ToolCall(id="1", name="bash", args={"command": "rm x"})
    ask = Ask("destructive", risk_level=RiskLevel.DESTRUCTIVE)
    store = ApprovalStore()
    prompt = ApprovalPrompt(choice="once")
    first = resolve_ask(
        call,
        ask,
        prompt=prompt,
        store=store,
        session_allowed_hashes=set(),
    )
    assert not isinstance(first, Deny)
    second = resolve_ask(
        call,
        ask,
        prompt=prompt,
        store=store,
        session_allowed_hashes=set(),
    )
    assert isinstance(second, Deny)


def test_deny_message_reaches_caller() -> None:
    call = ToolCall(id="1", name="bash", args={"command": "curl x"})
    ask = Ask("network", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    store = ApprovalStore()
    prompt = ApprovalPrompt(choice="deny", deny_message="blocked by user")
    result = resolve_ask(
        call,
        ask,
        prompt=prompt,
        store=store,
        session_allowed_hashes=set(),
    )
    assert isinstance(result, Deny)
    assert result.reason == "blocked by user"


def test_session_allowance_not_persisted_in_store() -> None:
    call = ToolCall(id="1", name="bash", args={"command": "rm a"})
    ask = Ask("rm", risk_level=RiskLevel.DESTRUCTIVE)
    store = ApprovalStore()
    session: set[str] = set()
    prompt = ApprovalPrompt(choice="session")
    resolve_ask(call, ask, prompt=prompt, store=store, session_allowed_hashes=session)
    assert tool_call_hash(call) in session
    assert store.status(call) is None
