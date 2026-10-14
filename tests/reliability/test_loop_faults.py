"""The agent loop under provider faults: no crash, no unintended tool execution."""

from pydantic import BaseModel

from codeagent.loop import run_agent_loop
from codeagent.providers.base import (
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallArgsDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.providers.faulty import Fault, FaultyProvider
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import ToolRegistry


class _PathArgs(BaseModel):
    path: str


def _registry(calls: list[str]) -> ToolRegistry:
    def _read(args: BaseModel) -> ToolResult:
        calls.append(str(args.model_dump()["path"]))
        return ToolResult(ok=True, summary="read", content="file", truncated=False)

    registry = ToolRegistry()
    registry.register(
        "read_file",
        "Read a file (test tool).",
        _PathArgs,
        _read,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    return registry


def _tool_turn() -> list[object]:
    return [
        ToolCallStart(id="c1", name="read_file"),
        ToolCallArgsDelta(id="c1", delta='{"path": "a.py"}'),
        ToolCallEnd(call=ToolCall(id="c1", name="read_file", args={"path": "a.py"})),
        Stop(reason=StopReason.TOOL_CALLS),
    ]


def _text_turn() -> list[object]:
    return [
        TextDelta(text="done"),
        UsageEvent(usage=Usage(input=1, output=1)),
        Stop(reason=StopReason.STOP),
    ]


def _run(faults: list[Fault], turns: list[list[object]], calls: list[str]):  # type: ignore[no-untyped-def]
    provider = FaultyProvider(FakeProvider(turns), faults)
    return run_agent_loop("goal", provider, _registry(calls), max_iterations=5)


def test_rate_limit_stops_the_run_without_crashing() -> None:
    calls: list[str] = []
    result = _run([Fault(kind="rate_limit", on_call=0)], [_text_turn()], calls)
    assert result.stop_reason == "provider_error"
    assert calls == []


def test_server_error_stops_the_run_without_crashing() -> None:
    calls: list[str] = []
    result = _run([Fault(kind="server_error", on_call=0)], [_text_turn()], calls)
    assert result.stop_reason == "provider_error"
    assert calls == []


def test_truncated_stream_does_not_execute_the_partial_tool_call() -> None:
    calls: list[str] = []
    _run([Fault(kind="truncate", on_call=0)], [_tool_turn(), _text_turn()], calls)
    assert calls == []


def test_malformed_tool_json_does_not_execute_or_crash() -> None:
    calls: list[str] = []
    result = _run(
        [Fault(kind="bad_tool_json", on_call=0)],
        [_tool_turn(), _text_turn()],
        calls,
    )
    assert calls == []
    assert result.stop_reason != "", "run must end with a defined stop reason"
