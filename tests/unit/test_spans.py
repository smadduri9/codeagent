"""Span support in the event emitter."""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from codeagent.observability.events import EventEmitter


@dataclass
class _ListSink:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def write(
        self,
        *,
        run_id: str,
        trace_id: str,
        span_id: str | None,
        name: str,
        payload: dict[str, Any] | None,
        parent_span_id: str | None = None,
    ) -> None:
        self.rows.append(
            {
                "name": name,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "payload": payload,
            },
        )


def _emitter() -> tuple[EventEmitter, _ListSink]:
    sink = _ListSink()
    return EventEmitter(run_id="r1", sinks=[sink]), sink


def test_nested_spans_form_a_tree() -> None:
    emitter, sink = _emitter()
    with emitter.span("run") as run_id:
        with emitter.span("tool.call", {"tool": "ls"}) as tool_id:
            emitter.emit("tool.completed", {"ok": True})
    by_name = {(r["name"], r["span_id"]): r for r in sink.rows}
    tool_start = next(r for r in sink.rows if r["name"] == "tool.call.start")
    assert tool_start["parent_span_id"] == run_id
    assert tool_start["span_id"] == tool_id
    completed = next(r for r in sink.rows if r["name"] == "tool.completed")
    assert completed["span_id"] == tool_id
    assert completed["parent_span_id"] == run_id
    end = next(r for r in sink.rows if r["name"] == "tool.call.end")
    assert end["payload"]["duration_ms"] >= 0
    assert by_name


def test_exception_is_recorded_and_reraised() -> None:
    emitter, sink = _emitter()
    with pytest.raises(ValueError):
        with emitter.span("run"):
            raise ValueError("boom")
    end = next(r for r in sink.rows if r["name"] == "run.end")
    assert end["payload"]["error.type"] == "ValueError"


def test_unknown_span_name_rejected() -> None:
    emitter, _sink = _emitter()
    with pytest.raises(ValueError):
        with emitter.span("not.a.span"):
            pass


def test_payload_is_json_serialisable() -> None:
    emitter, sink = _emitter()
    with emitter.span("run", {"goal_chars": 3}):
        pass
    json.dumps(sink.rows)
