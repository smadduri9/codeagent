"""Shared message, request, and streaming event types for providers."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from codeagent.tools.base import ToolSpec


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(StrictModel):
    id: str
    name: str
    args: dict[str, object] = Field(default_factory=dict)


class Message(StrictModel):
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class Usage(StrictModel):
    input: int = Field(ge=0)
    output: int = Field(ge=0)
    cache_read: int = Field(default=0, ge=0)
    cache_write: int = Field(default=0, ge=0)


class ModelRequest(StrictModel):
    system: str
    messages: list[Message]
    tools: list[ToolSpec]
    model: str
    max_output_tokens: int = Field(gt=0)
    temperature: float = 0.0


class TextDelta(StrictModel):
    kind: Literal["text_delta"] = "text_delta"
    text: str


class ToolCallStart(StrictModel):
    kind: Literal["tool_call_start"] = "tool_call_start"
    id: str
    name: str


class ToolCallArgsDelta(StrictModel):
    kind: Literal["tool_call_args_delta"] = "tool_call_args_delta"
    id: str
    delta: str


class ToolCallEnd(StrictModel):
    kind: Literal["tool_call_end"] = "tool_call_end"
    call: ToolCall


class UsageEvent(StrictModel):
    kind: Literal["usage"] = "usage"
    usage: Usage


class StopReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class Stop(StrictModel):
    kind: Literal["stop"] = "stop"
    reason: StopReason


ModelEvent = Annotated[
    TextDelta | ToolCallStart | ToolCallArgsDelta | ToolCallEnd | UsageEvent | Stop,
    Field(discriminator="kind"),
]
