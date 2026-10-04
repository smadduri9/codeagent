"""Tool specification and result types."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal[
    "READ_ONLY",
    "LOCAL_MUTATION",
    "EXTERNAL_SIDE_EFFECT",
    "DESTRUCTIVE",
    "FORBIDDEN",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StrictArgs(StrictModel):
    """Base class for tool argument models."""


class ToolSpec(StrictModel):
    name: str
    description: str
    parameters: dict[str, object] = Field(default_factory=dict)
    risk_level: RiskLevel | None = None


class ToolResult(StrictModel):
    ok: bool
    summary: str
    content: str
    truncated: bool
    exit_code: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
