from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

from codeagent.observability.redact import redact_payload

EVENT_NAMES = frozenset(
    {
        "run.started",
        "run.phase_changed",
        "run.completed",
        "run.failed",
        "model.request",
        "model.response",
        "context.built",
        "context.compacted",
        "tool.requested",
        "policy.decision",
        "approval.requested",
        "approval.resolved",
        "tool.started",
        "tool.completed",
        "file.changed",
        "verification.started",
        "verification.check",
        "verification.completed",
        "plan.updated",
        "failure.classified",
        "budget.warning",
        "checkpoint.created",
    },
)

SPAN_NAMES = frozenset({"run", "model.call", "tool.call", "context.compact", "verify.check"})


class EventSink(Protocol):
    def write(
        self,
        *,
        run_id: str,
        trace_id: str,
        span_id: str | None,
        name: str,
        payload: dict[str, Any] | None,
        parent_span_id: str | None = None,
    ) -> None: ...


@dataclass
class EventEmitter:
    run_id: str
    sinks: list[EventSink]
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _stack: list[str] = field(default_factory=list)
    _annotations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def emit(self, name: str, payload: dict[str, Any] | None = None) -> None:
        if name not in EVENT_NAMES:
            raise ValueError(name)
        current = self._stack[-1] if self._stack else None
        parent = self._stack[-2] if len(self._stack) > 1 else None
        self._write(name, payload, current, parent)

    @contextmanager
    def span(self, name: str, payload: dict[str, Any] | None = None) -> Iterator[str]:
        if name not in SPAN_NAMES:
            raise ValueError(name)
        span_id = uuid.uuid4().hex[:16]
        parent = self._stack[-1] if self._stack else None
        self._write(f"{name}.start", payload, span_id, parent)
        self._stack.append(span_id)
        started = time.perf_counter()
        end_payload: dict[str, Any] = {}
        try:
            yield span_id
        except BaseException as exc:
            end_payload["error.type"] = type(exc).__name__
            raise
        finally:
            self._stack.pop()
            end_payload["duration_ms"] = int((time.perf_counter() - started) * 1000)
            end_payload.update(self._annotations.pop(span_id, {}))
            self._write(f"{name}.end", end_payload, span_id, parent)

    def annotate(self, payload: dict[str, Any]) -> None:
        """Merge keys into the current span's end event; ignored outside a span."""
        if self._stack:
            self._annotations.setdefault(self._stack[-1], {}).update(payload)

    def _write(
        self,
        name: str,
        payload: dict[str, Any] | None,
        span_id: str | None,
        parent_span_id: str | None,
    ) -> None:
        cleaned = redact_payload(payload)
        for sink in self.sinks:
            sink.write(
                run_id=self.run_id,
                trace_id=self.trace_id,
                span_id=span_id,
                name=name,
                payload=cleaned,
                parent_span_id=parent_span_id,
            )
