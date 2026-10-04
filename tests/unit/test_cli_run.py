"""CLI run command integration."""

from pathlib import Path

from pydantic import TypeAdapter
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.providers.base import (
    ModelEvent,
    Stop,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    UsageEvent,
)


def test_run_with_fake_script(tmp_path: Path) -> None:
    script: list[list[ModelEvent]] = [
        [
            ToolCallStart(id="c1", name="echo"),
            ToolCallEnd(call=ToolCall(id="c1", name="echo", args={"message": "hi"})),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.TOOL_CALLS),
        ],
        [
            TextDelta(text="done"),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.STOP),
        ],
    ]
    adapter = TypeAdapter(list[list[ModelEvent]])
    adapter_path = tmp_path / "script.json"
    adapter_path.write_bytes(adapter.dump_json(script))
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "test goal", "--fake-script", str(adapter_path)],
    )
    assert result.exit_code == 0
    assert "stop" in result.stderr
