"""Permission decision and risk types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_MUTATION = "local_mutation"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    DESTRUCTIVE = "destructive"
    FORBIDDEN = "forbidden"


DecidedBy = Literal["rule", "user"]


@dataclass(frozen=True, slots=True)
class Allow:
    risk_level: RiskLevel
    decided_by: DecidedBy = "rule"


@dataclass(frozen=True, slots=True)
class Ask:
    reason: str
    risk_level: RiskLevel | None = None


@dataclass(frozen=True, slots=True)
class Deny:
    reason: str
    risk_level: RiskLevel | None = None


Decision = Allow | Ask | Deny


def strictest(*decisions: Decision) -> Decision:
    """Pick the strictest decision (deny over ask over allow)."""
    result: Decision = Allow(risk_level=RiskLevel.READ_ONLY)
    for item in decisions:
        if isinstance(item, Deny):
            return item
        if isinstance(item, Ask):
            result = item
    return result


def is_allow(decision: Decision) -> bool:
    return isinstance(decision, Allow)


def is_ask(decision: Decision) -> bool:
    return isinstance(decision, Ask)


def is_deny(decision: Decision) -> bool:
    return isinstance(decision, Deny)
