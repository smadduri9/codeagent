"""Interactive vs non-interactive permission resolution."""

from __future__ import annotations

from codeagent.permissions.types import Ask, Decision, Deny


def resolve_non_interactive(decision: Decision, *, interactive: bool) -> Decision:
    """Turn Ask into Deny when the session is non-interactive."""
    if interactive or not isinstance(decision, Ask):
        return decision
    return Deny(decision.reason, risk_level=decision.risk_level)
