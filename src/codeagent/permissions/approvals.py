"""Single-use approval records bound to tool argument hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from codeagent.permissions.types import Allow, Ask, Decision, Deny, RiskLevel
from codeagent.providers.base import ToolCall


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    USED = "used"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    tool_call_hash: str
    status: ApprovalStatus
    deny_message: str | None = None


def tool_call_hash(call: ToolCall) -> str:
    payload = json.dumps(
        {"name": call.name, "args": call.args},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class ApprovalStore:
    """In-memory approval records for a run (not persisted)."""

    records: dict[str, ApprovalRecord] = field(default_factory=dict)

    def status(self, call: ToolCall) -> ApprovalStatus | None:
        record = self.records.get(tool_call_hash(call))
        return record.status if record else None

    def mark_approved(self, call: ToolCall) -> None:
        digest = tool_call_hash(call)
        self.records[digest] = ApprovalRecord(
            tool_call_hash=digest,
            status=ApprovalStatus.APPROVED,
        )

    def mark_denied(self, call: ToolCall, message: str | None = None) -> None:
        digest = tool_call_hash(call)
        self.records[digest] = ApprovalRecord(
            tool_call_hash=digest,
            status=ApprovalStatus.DENIED,
            deny_message=message,
        )

    def consume(self, call: ToolCall) -> bool:
        """Mark an approved record as used; reject replay."""
        digest = tool_call_hash(call)
        record = self.records.get(digest)
        if record is None or record.status is not ApprovalStatus.APPROVED:
            return False
        self.records[digest] = ApprovalRecord(
            tool_call_hash=digest,
            status=ApprovalStatus.USED,
        )
        return True


ApprovalChoice = Literal["once", "deny", "session"]


class ApprovalResponder(Protocol):
    choice: ApprovalChoice

    def resolve(self, call: ToolCall, ask: Ask) -> Decision: ...


@dataclass
class ApprovalPrompt:
    """Stub approval UI for tests and CLI hooks."""

    choice: ApprovalChoice = "deny"
    deny_message: str | None = None

    def resolve(self, _call: ToolCall, ask: Ask) -> Decision:
        if self.choice == "once":
            level = ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT
            return Allow(risk_level=level, decided_by="user")
        if self.choice == "session":
            level = ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT
            return Allow(risk_level=level, decided_by="user")
        return Deny(
            self.deny_message or ask.reason,
            risk_level=ask.risk_level,
        )


def resolve_ask(
    call: ToolCall,
    ask: Ask,
    *,
    prompt: ApprovalResponder,
    store: ApprovalStore,
    session_allowed_hashes: set[str],
) -> Decision:
    digest = tool_call_hash(call)
    status = store.status(call)
    if status is ApprovalStatus.USED:
        return Deny("approval already used", risk_level=ask.risk_level)
    if digest in session_allowed_hashes:
        return Allow(
            risk_level=ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT,
            decided_by="user",
        )

    resolved = prompt.resolve(call, ask)
    if isinstance(resolved, Deny):
        store.mark_denied(call, resolved.reason)
        return resolved
    if prompt.choice == "session":
        session_allowed_hashes.add(digest)
        return resolved
    if prompt.choice == "once":
        store.mark_approved(call)
        if not store.consume(call):
            return Deny("approval could not be consumed", risk_level=ask.risk_level)
        return resolved
    return resolved
