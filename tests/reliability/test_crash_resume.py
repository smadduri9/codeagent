"""A process killed mid tool call can be resumed without double execution."""

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.state.session import INTERRUPTED_MSG, prepare_resume
from codeagent.state.store import StateStore

_DRIVER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from pydantic import BaseModel
    from codeagent.config import Settings
    from codeagent.providers.base import (
        Stop, StopReason, ToolCall, ToolCallEnd, ToolCallStart, Usage, UsageEvent,
    )
    from codeagent.providers.fake import FakeProvider
    from codeagent.state.session import begin_persisted_run, run_with_persistence
    from codeagent.state.store import StateStore
    from codeagent.tools.base import ToolResult
    from codeagent.tools.registry import ToolRegistry

    class Args(BaseModel):
        path: str

    def write(args):
        Path(sys.argv[2]).write_text(args.path)
        return ToolResult(ok=True, summary="w", content="ok", truncated=False)

    root = Path(sys.argv[1])
    store = StateStore(root / "state.db")
    ctx = begin_persisted_run(store, repo_root=root, goal="g", model="m", settings=Settings())
    registry = ToolRegistry()
    registry.register("write_file", "Write (test).", Args, write,
        parameters={"type": "object", "properties": {"path": {"type": "string"}},
                    "required": ["path"], "additionalProperties": False})
    provider = FakeProvider([[
        ToolCallStart(id="c1", name="write_file"),
        ToolCallEnd(call=ToolCall(id="c1", name="write_file", args={"path": "x"})),
        UsageEvent(usage=Usage(input=1, output=1)),
        Stop(reason=StopReason.TOOL_CALLS),
    ]])
    run_with_persistence("g", provider, registry, ctx, max_iterations=3)
    """
)


@pytest.mark.slow
@pytest.mark.skipif(os.name != "posix", reason="SIGKILL is POSIX-only")
@pytest.mark.parametrize("attempt", range(5))
def test_crash_mid_tool_then_resume_closes_the_call(attempt: int, tmp_path: Path) -> None:
    del attempt  # repeated five times to show the result is stable
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    marker = tmp_path / "marker.txt"
    env = {**os.environ, "CODEAGENT_TEST_CRASH_AT": "tool_started"}
    completed = subprocess.run(
        [sys.executable, str(driver), str(tmp_path), str(marker)],
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == -signal.SIGKILL
    assert not marker.exists(), "the tool must not have run before the crash"

    store = StateStore(tmp_path / "state.db")
    run_id = store.list_runs(limit=1)[0].id
    resumed, history, warnings = prepare_resume(store, run_id, settings=Settings())
    rows = [r for r in store.list_tool_calls(run_id) if r["tool"] == "write_file"]
    assert rows[0]["ok"] == 0
    assert INTERRUPTED_MSG in (rows[0]["result_json"] or "")
    assert any("interrupted" in w for w in warnings)
    assert marker.exists() is False
    resumed.store.close()
