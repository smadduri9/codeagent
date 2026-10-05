from __future__ import annotations

import uuid
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


class EventSink(Protocol):
    def write(
        self,
        *,
        run_id: str,
        trace_id: str,
        span_id: str | None,
        name: str,
        payload: dict[str, Any] | None,
    ) -> None: ...


@dataclass
class EventEmitter:
    run_id: str
    sinks: list[EventSink]
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def emit(self, name: str, payload: dict[str, Any] | None = None) -> None:
        if name not in EVENT_NAMES:
            raise ValueError(name)
        cleaned = redact_payload(payload)
        for sink in self.sinks:
            sink.write(
                run_id=self.run_id,
                trace_id=self.trace_id,
                span_id=None,
                name=name,
                payload=cleaned,
            )
