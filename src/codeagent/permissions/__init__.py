"""Deterministic permission engine."""

from codeagent.permissions.approvals import (
    ApprovalPrompt,
    ApprovalStore,
    resolve_ask,
    tool_call_hash,
)
from codeagent.permissions.engine import decide
from codeagent.permissions.mode import resolve_non_interactive
from codeagent.permissions.run_context import PermissionRun
from codeagent.permissions.shell_classify import classify_shell
from codeagent.permissions.shell_parse import parse_shell
from codeagent.permissions.types import Allow, Ask, Decision, Deny, RiskLevel
from codeagent.permissions.untrusted import (
    UNTRUSTED_END,
    UNTRUSTED_START,
    UNTRUSTED_SYSTEM_NOTE,
    wrap_untrusted,
)

__all__ = [
    "Allow",
    "ApprovalPrompt",
    "ApprovalStore",
    "Ask",
    "Deny",
    "Decision",
    "PermissionRun",
    "RiskLevel",
    "UNTRUSTED_END",
    "UNTRUSTED_START",
    "UNTRUSTED_SYSTEM_NOTE",
    "classify_shell",
    "decide",
    "parse_shell",
    "resolve_ask",
    "resolve_non_interactive",
    "tool_call_hash",
    "wrap_untrusted",
]
