"""Model-call spans carry the input breakdown, billed usage and latency."""

import json
from pathlib import Path

from codeagent.config import Settings
from codeagent.context.manager import ContextManager
from codeagent.loop import run_agent_loop
from codeagent.observability.run_emitter import build_run_emitter
from codeagent.providers.base import Stop, StopReason, TextDelta, Usage, UsageEvent
from codeagent.providers.fake import FakeProvider
from codeagent.state.recorder import RunRecorder
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry


def test_model_call_end_has_breakdown_usage_and_latency(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    recorder = RunRecorder(
        store, run_id, tmp_path, emitter=build_run_emitter(store, run_id, tmp_path)
    )
    provider = FakeProvider(
        [
            [
                TextDelta(text="hi"),
                UsageEvent(usage=Usage(input=100, output=10, cache_read=40, cache_write=5)),
                Stop(reason=StopReason.STOP),
            ],
        ],
    )
    context = ContextManager(settings=Settings(), instructions="be brief")
    run_agent_loop(
        "g",
        provider,
        ToolRegistry(),
        max_iterations=3,
        recorder=recorder,
        run_id=run_id,
        context=context,
    )
    ends = [e for e in store.list_events(run_id) if e.name == "model.call.end"]
    assert len(ends) == 1
    payload = json.loads(ends[0].payload_json or "{}")
    assert payload["usage.input"] == 100
    assert payload["usage.cache_write"] == 5
    assert payload["usage.cache_read"] == 40
    assert payload["latency.ttft_ms"] <= payload["latency.total_ms"]
    assert payload["stop_reason"] == "stop"
    assert payload["prefix_hash"]
    segments = [k for k in payload if k.startswith("est.")]
    assert {"est.system_base", "est.instructions", "est.tools", "est.history"} <= set(segments)
    assert payload["est_error"] is not None
    store.close()
