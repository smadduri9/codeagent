from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeagent.state.store import StateStore


@dataclass(frozen=True, slots=True)
class JsonlEventSink:
    path: Path

    def write(
        self,
        *,
        run_id: str,
        trace_id: str,
        span_id: str | None,
        name: str,
        payload: dict[str, Any] | None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"run_id": run_id, "trace_id": trace_id, "name": name, "payload": payload}
                )
                + "\n"
            )


@dataclass(frozen=True, slots=True)
class DatabaseEventSink:
    store: StateStore

    def write(
        self,
        *,
        run_id: str,
        trace_id: str,
        span_id: str | None,
        name: str,
        payload: dict[str, Any] | None,
    ) -> None:
        self.store.record_event(run_id, name, payload, trace_id=trace_id, span_id=span_id)
