"""Tool specification and result types."""

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolSpec(StrictModel):
    name: str
    description: str
    parameters: dict[str, object] = Field(default_factory=dict)


class ToolResult(StrictModel):
    ok: bool
    summary: str
    content: str
    truncated: bool
    exit_code: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
