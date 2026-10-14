"""Run statistics computed from stored events. Pure functions, no I/O."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from codeagent.state.store import StoredEvent


@dataclass(frozen=True)
class RunStats:
    model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cache_hit_ratio: float
    wall_ms: int
    segment_share: dict[str, float] = field(default_factory=dict)
    per_tool: dict[str, dict[str, int]] = field(default_factory=dict)
    input_by_iteration: list[int] = field(default_factory=list)
    denied_calls: int = 0


def _payload(event: StoredEvent) -> dict[str, Any]:
    return json.loads(event.payload_json) if event.payload_json else {}


def compute_stats(events: list[StoredEvent]) -> RunStats:
    tool_by_span: dict[str, str] = {}
    for event in events:
        if event.name == "tool.call.start" and event.span_id:
            tool_by_span[event.span_id] = str(_payload(event).get("tool", "unknown"))

    model_ends = [_payload(e) for e in events if e.name == "model.call.end"]
    segments: dict[str, int] = defaultdict(int)
    per_tool: dict[str, dict[str, int]] = {}
    tool_calls = 0
    wall_ms = 0
    denied = 0
    for event in events:
        if event.name == "tool.call.end":
            tool_calls += 1
            tool = tool_by_span.get(event.span_id or "", "unknown")
            row = per_tool.setdefault(tool, {"calls": 0, "total_ms": 0})
            row["calls"] += 1
            row["total_ms"] += int(_payload(event).get("duration_ms", 0))
        elif event.name == "run.end":
            wall_ms = int(_payload(event).get("duration_ms", 0))
        elif event.name == "policy.decision" and _payload(event).get("kind") == "deny":
            denied += 1

    for payload in model_ends:
        for key, value in payload.items():
            if key.startswith("est."):
                segments[key[len("est.") :]] += int(value or 0)

    input_tokens = sum(int(p.get("usage.input", 0) or 0) for p in model_ends)
    cache_read = sum(int(p.get("usage.cache_read", 0) or 0) for p in model_ends)
    cache_write = sum(int(p.get("usage.cache_write", 0) or 0) for p in model_ends)
    denominator = input_tokens + cache_read + cache_write
    total_segments = sum(segments.values())
    return RunStats(
        model_calls=len(model_ends),
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=sum(int(p.get("usage.output", 0) or 0) for p in model_ends),
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        cache_hit_ratio=cache_read / denominator if denominator else 0.0,
        wall_ms=wall_ms,
        segment_share={
            name: round(100.0 * value / total_segments, 2)
            for name, value in segments.items()
            if total_segments
        },
        per_tool=per_tool,
        input_by_iteration=[int(p.get("usage.input", 0) or 0) for p in model_ends],
        denied_calls=denied,
    )


def stats_as_json(stats: RunStats) -> str:
    return json.dumps(asdict(stats), indent=2, sort_keys=True)
