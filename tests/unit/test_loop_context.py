"""ContextManager is used by the agent loop when supplied."""

from pydantic import BaseModel

from codeagent.config import RequestSettings, Settings
from codeagent.context.manager import ContextManager
from codeagent.loop import run_agent_loop
from codeagent.providers.base import (
    MessageRole,
    ModelRequest,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import ToolRegistry

_BIG = "x" * 2000


class _BigArgs(BaseModel):
    n: int


def _big_handler(_args: BaseModel) -> ToolResult:
    return ToolResult(ok=True, summary="big", content=_BIG, truncated=False)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "big",
        "Return a large fixed output (test tool).",
        _BigArgs,
        _big_handler,
        parameters={
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
            "additionalProperties": False,
        },
    )
    return registry


class _RecordingProvider(FakeProvider):
    def __init__(self, turns: list[list[object]]) -> None:
        super().__init__(turns)  # type: ignore[arg-type]
        self.seen: list[ModelRequest] = []

    def stream(self, req: ModelRequest):  # type: ignore[no-untyped-def]
        self.seen.append(req)
        return super().stream(req)


def _tool_turn(call_id: str) -> list[object]:
    # Distinct args per call: identical repeated calls trip the repeat guard.
    n = int(call_id[1:])
    return [
        ToolCallStart(id=call_id, name="big"),
        ToolCallEnd(call=ToolCall(id=call_id, name="big", args={"n": n})),
        UsageEvent(usage=Usage(input=1, output=1)),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


def _turns() -> list[list[object]]:
    return [
        _tool_turn("c1"),
        _tool_turn("c2"),
        _tool_turn("c3"),
        _tool_turn("c4"),
        [
            TextDelta(text="done"),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.STOP),
        ],
    ]


def _chars(req: ModelRequest) -> int:
    return sum(len(m.content or "") for m in req.messages)


def test_context_manager_compacts_history_sent_to_model() -> None:
    settings = Settings(request=RequestSettings(max_request_tokens=200))
    context = ContextManager(settings=settings, instructions="")
    provider = _RecordingProvider(_turns())
    result = run_agent_loop(
        "go",
        provider,
        _registry(),
        max_iterations=10,
        context=context,
    )
    assert result.stop_reason == StopReason.STOP.value
    last = provider.seen[-1]
    assert _chars(last) < 4 * len(_BIG)


def test_without_context_full_history_is_sent() -> None:
    provider = _RecordingProvider(_turns())
    run_agent_loop("go", provider, _registry(), max_iterations=10)
    last = provider.seen[-1]
    tool_messages = [m for m in last.messages if m.role is MessageRole.TOOL]
    assert len(tool_messages) == 4
    assert _chars(last) > 4 * len(_BIG)
