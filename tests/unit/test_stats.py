"""codeagent stats: pure computation over stored events."""

import json
import re

from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.state.store import StoredEvent
from codeagent.stats import compute_stats, stats_as_json


def _ev(i: int, name: str, span: str | None, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        id=i,
        run_id="r",
        trace_id=None,
        span_id=span,
        name=name,
        ts="t",
        payload_json=json.dumps(payload),
    )


def _events() -> list[StoredEvent]:
    return [
        _ev(1, "model.call.start", "m1", {"model": "m"}),
        _ev(
            2,
            "model.call.end",
            "m1",
            {
                "usage.input": 100,
                "usage.output": 10,
                "usage.cache_read": 60,
                "usage.cache_write": 20,
                "est.history": 30,
                "est.tools": 10,
            },
        ),
        _ev(3, "tool.call.start", "t1", {"tool": "read_file", "call_id": "c1"}),
        _ev(4, "tool.call.end", "t1", {"duration_ms": 7}),
        _ev(5, "policy.decision", None, {"tool": "bash", "kind": "deny"}),
        _ev(6, "model.call.end", "m2", {"usage.input": 50, "usage.output": 5, "est.history": 0}),
        _ev(7, "run.end", "r0", {"duration_ms": 1234}),
    ]


def test_totals_and_cache_ratio() -> None:
    stats = compute_stats(_events())
    assert stats.model_calls == 2
    assert stats.tool_calls == 1
    assert stats.input_tokens == 150
    assert stats.output_tokens == 15
    assert stats.cache_read_tokens == 60
    assert stats.cache_write_tokens == 20
    assert round(stats.cache_hit_ratio, 4) == round(60 / (150 + 60 + 20), 4)
    assert stats.wall_ms == 1234


def test_segment_share_per_tool_and_iterations() -> None:
    stats = compute_stats(_events())
    assert stats.segment_share == {"history": 75.0, "tools": 25.0}
    assert stats.per_tool == {"read_file": {"calls": 1, "total_ms": 7}}
    assert stats.input_by_iteration == [100, 50]
    assert stats.denied_calls == 1


def test_json_output_is_valid() -> None:
    data = json.loads(stats_as_json(compute_stats(_events())))
    assert data["model_calls"] == 2
    assert data["segment_share"]["history"] == 75.0


def test_stats_command_help() -> None:
    result = CliRunner().invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    # Rich adds colour codes around option names on CI; strip them before matching.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--json" in plain
