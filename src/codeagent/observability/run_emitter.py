"""Wire trace sinks for a persisted run."""

from __future__ import annotations

from pathlib import Path

from codeagent.observability.events import EventEmitter
from codeagent.observability.reconstruct import trace_jsonl_path
from codeagent.observability.sink import DatabaseEventSink, JsonlEventSink
from codeagent.permissions.types import Allow, Ask, Decision, Deny
from codeagent.state.store import StateStore


def build_run_emitter(store: StateStore, run_id: str, repo_root: Path) -> EventEmitter:
    """Database + JSONL sinks for one run (DESIGN 8.16)."""
    return EventEmitter(
        run_id,
        [
            DatabaseEventSink(store),
            JsonlEventSink(trace_jsonl_path(repo_root, run_id)),
        ],
    )


def decision_payload(decision: Decision) -> dict[str, str]:
    if isinstance(decision, Allow):
        return {"kind": "allow", "risk_level": decision.risk_level.value}
    if isinstance(decision, Ask):
        return {"kind": "ask", "reason": decision.reason}
    if isinstance(decision, Deny):
        return {"kind": "deny", "reason": decision.reason}
    raise TypeError(type(decision))
