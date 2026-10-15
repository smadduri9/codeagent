"""A tool call with invalid arguments is denied and recorded; it must not crash the run."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.loop.policy import PolicyGate
from codeagent.permissions import PermissionRun
from codeagent.providers.base import (
    MessageRole,
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
from codeagent.state.session import begin_persisted_run, run_with_persistence
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry

# read_file with a non-integer limit, as a model actually produced in a live run.
_BAD = ToolCall(id="c1", name="read_file", args={"path": "a.py", "limit": "0>\n"})


def test_invalid_args_are_recorded_as_a_decision(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path)
    recorded: list[str] = []
    gate = PolicyGate(run=PermissionRun(workspace=tmp_path, settings=Settings()), registry=registry)
    gate.on_record = lambda record: recorded.append(record.call.id)
    decision, message = gate.evaluate(_BAD)
    assert recorded == ["c1"]
    assert message


def test_persisted_run_survives_invalid_tool_args(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    store = StateStore(tmp_path / "state.db")
    ctx = begin_persisted_run(store, repo_root=tmp_path, goal="g", model="m", settings=Settings())
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path)
    policy = PolicyGate(
        run=PermissionRun(workspace=tmp_path, settings=Settings()), registry=registry
    )
    provider = FakeProvider(
        [
            [
                ToolCallStart(id="c1", name="read_file"),
                ToolCallEnd(call=_BAD),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.TOOL_CALLS),
            ],
            [
                TextDelta(text="done"),
                UsageEvent(usage=Usage(input=1, output=1)),
                Stop(reason=StopReason.STOP),
            ],
        ],
    )
    result = run_with_persistence("g", provider, registry, ctx, max_iterations=5, policy=policy)
    assert result.stop_reason == StopReason.STOP.value
    tool_messages = [m for m in result.history if m.role is MessageRole.TOOL]
    assert tool_messages and tool_messages[0].tool_call_id == "c1"
    store.close()
