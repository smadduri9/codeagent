"""Security: a used approval never carries over; the operator is asked again."""

from __future__ import annotations

from dataclasses import dataclass, field

from codeagent.permissions import ApprovalStore, Ask, Deny, resolve_ask
from codeagent.permissions.approvals import ApprovalChoice
from codeagent.permissions.types import Allow, Decision, RiskLevel
from codeagent.providers.base import ToolCall


@dataclass
class _ScriptedPrompt:
    """Answers each prompt from a list and counts how often it was consulted."""

    answers: list[ApprovalChoice]
    choice: ApprovalChoice = "deny"
    asked: list[str] = field(default_factory=list)

    def resolve(self, call: ToolCall, ask: Ask) -> Decision:
        self.asked.append(call.name)
        self.choice = self.answers.pop(0)
        if self.choice == "deny":
            return Deny(ask.reason, risk_level=ask.risk_level)
        return Allow(risk_level=ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT, decided_by="user")


_CALL = ToolCall(id="1", name="bash", args={"command": "pytest -q"})
_ASK = Ask("unknown command", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)


def _resolve(prompt: _ScriptedPrompt, store: ApprovalStore, session: set[str]) -> Decision:
    return resolve_ask(_CALL, _ASK, prompt=prompt, store=store, session_allowed_hashes=session)


def test_identical_call_after_once_approval_asks_again() -> None:
    prompt = _ScriptedPrompt(answers=["once", "once"])
    store, session = ApprovalStore(), set[str]()
    assert isinstance(_resolve(prompt, store, session), Allow)
    assert isinstance(_resolve(prompt, store, session), Allow)
    assert len(prompt.asked) == 2


def test_used_approval_is_never_reused_without_a_new_answer() -> None:
    prompt = _ScriptedPrompt(answers=["once", "deny"])
    store, session = ApprovalStore(), set[str]()
    assert isinstance(_resolve(prompt, store, session), Allow)
    second = _resolve(prompt, store, session)
    assert isinstance(second, Deny)
    assert second.reason == "unknown command"
    assert len(prompt.asked) == 2


def test_once_approval_does_not_become_a_session_allowance() -> None:
    prompt = _ScriptedPrompt(answers=["once"])
    store, session = ApprovalStore(), set[str]()
    _resolve(prompt, store, session)
    assert session == set()


def test_session_allowance_does_not_ask_again() -> None:
    prompt = _ScriptedPrompt(answers=["session"])
    store, session = ApprovalStore(), set[str]()
    assert isinstance(_resolve(prompt, store, session), Allow)
    assert isinstance(_resolve(prompt, store, session), Allow)
    assert len(prompt.asked) == 1


def test_store_consume_still_rejects_replay() -> None:
    store = ApprovalStore()
    store.mark_approved(_CALL)
    assert store.consume(_CALL)
    assert not store.consume(_CALL)
