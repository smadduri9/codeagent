"""Policy gate: validate, decide, record, then execute."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from codeagent.permissions.approvals import ApprovalPrompt, ApprovalStore, resolve_ask
from codeagent.permissions.engine import decide
from codeagent.permissions.mode import resolve_non_interactive
from codeagent.permissions.run_context import PermissionRun
from codeagent.permissions.types import Ask, Decision, Deny, is_allow
from codeagent.permissions.untrusted import wrap_untrusted
from codeagent.providers.base import ToolCall
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import ToolRegistry, ToolValidationError, UnknownToolError


@dataclass
class RecordedDecision:
    call: ToolCall
    decision: Decision
    recorded_before_execution: bool = True


@dataclass
class PolicyGate:
    run: PermissionRun
    registry: ToolRegistry
    approval_store: ApprovalStore = field(default_factory=ApprovalStore)
    approval_prompt: ApprovalPrompt | None = None
    decisions: list[RecordedDecision] = field(default_factory=list)
    executed_calls: list[ToolCall] = field(default_factory=list)
    on_record: Callable[[RecordedDecision], None] | None = None

    def evaluate(self, call: ToolCall) -> tuple[Decision, str | None]:
        """Validate arguments, decide, record, and resolve approvals."""
        try:
            validated = self.registry.validate(call)
        except (ToolValidationError, UnknownToolError) as exc:
            return Deny(str(exc)), None

        raw_decision = decide(call, validated, self.run)
        decision = resolve_non_interactive(
            raw_decision,
            interactive=self.run.interactive,
        )
        if isinstance(decision, Ask) and self.approval_prompt is not None:
            decision = resolve_ask(
                call,
                decision,
                prompt=self.approval_prompt,
                store=self.approval_store,
                session_allowed_hashes=self.run.session_allowed_hashes,
            )
        elif isinstance(decision, Ask):
            decision = resolve_non_interactive(decision, interactive=False)

        record = RecordedDecision(call=call, decision=decision)
        self.decisions.append(record)
        if self.on_record is not None:
            self.on_record(record)

        deny_message: str | None = None
        if isinstance(decision, Deny):
            deny_message = decision.reason
        return decision, deny_message

    def execute_allowed(self, call: ToolCall, decision: Decision) -> ToolResult:
        if not is_allow(decision):
            raise RuntimeError("execute_allowed called without allow decision")
        if not self.decisions:
            raise RuntimeError("no decision recorded before execution")
        last = self.decisions[-1]
        if last.call.id != call.id or not is_allow(last.decision):
            raise RuntimeError("decision record mismatch before execution")
        self.executed_calls.append(call)
        try:
            validated = self.registry.validate(call)
            result = self.registry.run_validated(call, validated)
        except (ToolValidationError, UnknownToolError) as exc:
            result = self.registry.tool_error(call, str(exc))
        return result

    def denied_result(self, call: ToolCall, message: str) -> ToolResult:
        return self.registry.tool_error(call, message)

    def wrap_result(self, result: ToolResult) -> str:
        return wrap_untrusted(result.content)
