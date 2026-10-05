"""Hook run lifecycle and loop events into the state store."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeagent.lifecycle import RunPhase
from codeagent.loop.policy import RecordedDecision
from codeagent.observability.events import EventEmitter
from codeagent.observability.run_emitter import decision_payload
from codeagent.permissions.types import Decision
from codeagent.providers.base import Message, ToolCall, Usage
from codeagent.state.store import StateStore, args_hash_for_tool
from codeagent.tools.read_tracker import content_hash


@dataclass
class RunRecorder:
    store: StateStore
    run_id: str
    repo_root: Path
    emitter: EventEmitter | None = None
    _step_index: int = 0
    _current_step_id: int | None = None
    _pending_tools: dict[str, int] = field(default_factory=dict)

    def emit(self, name: str, payload: dict[str, Any] | None = None) -> None:
        if self.emitter is not None:
            self.emitter.emit(name, payload)

    def on_phase(self, phase: RunPhase) -> None:
        self.store.update_run_phase(self.run_id, phase)
        self.emit("run.phase_changed", {"phase": phase.value})

    def on_assistant_step(
        self,
        assistant: Message,
        usage: Usage | None,
        *,
        cost_usd: float,
        latency_ms: int | None,
        prompt_hash: str | None = None,
    ) -> int:
        tokens_in = usage.input if usage else 0
        tokens_out = usage.output if usage else 0
        cache_read = usage.cache_read if usage else 0
        step_id = self.store.insert_step(
            self.run_id,
            idx=self._step_index,
            assistant=assistant,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_read=cache_read,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            prompt_hash=prompt_hash,
        )
        self._step_index += 1
        self._current_step_id = step_id
        return step_id

    def on_decision(self, record: RecordedDecision) -> None:
        if self._current_step_id is None:
            raise RuntimeError("assistant step must be recorded before tool decisions")
        self.emit(
            "policy.decision",
            {
                "tool": record.call.name,
                "call_id": record.call.id,
                **decision_payload(record.decision),
            },
        )
        tool_id = self.store.begin_tool_call(
            self.run_id,
            self._current_step_id,
            record.call,
            record.decision,
        )
        self._pending_tools[record.call.id] = tool_id

    def record_legacy_decision(self, call: ToolCall, allowed: bool) -> int:
        if self._current_step_id is None:
            raise RuntimeError("assistant step must be recorded before tool decisions")
        from codeagent.permissions.types import Allow, Deny, RiskLevel

        decision: Decision = Allow(risk_level=RiskLevel.READ_ONLY) if allowed else Deny("denied")
        self.emit(
            "policy.decision",
            {
                "tool": call.name,
                "call_id": call.id,
                **decision_payload(decision),
            },
        )
        tool_id = self.store.begin_tool_call(
            self.run_id,
            self._current_step_id,
            call,
            decision,
        )
        self._pending_tools[call.id] = tool_id
        return tool_id

    def complete_tool(
        self,
        call: ToolCall,
        *,
        ok: bool,
        result_content: str,
        duration_ms: int,
    ) -> None:
        tool_id = self._pending_tools.pop(call.id, None)
        if tool_id is None:
            raise RuntimeError(f"no pending tool row for {call.id}")
        self.store.complete_tool_call(
            tool_id,
            ok=ok,
            result_content=result_content,
            duration_ms=duration_ms,
        )
        self.emit(
            "tool.completed",
            {
                "tool": call.name,
                "call_id": call.id,
                "ok": ok,
                "duration_ms": duration_ms,
            },
        )

    def record_file_read(self, path: Path, content: str) -> None:
        rel = path.as_posix()
        try:
            rel = path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
        self.store.record_file_read(self.run_id, Path(rel), content_hash(content))

    def finish(
        self,
        phase: RunPhase,
        stop_reason: str | None,
        *,
        resumable: bool = False,
    ) -> None:
        terminal = {
            "phase": phase.value,
            "stop_reason": stop_reason,
            "resumable": resumable,
        }
        if phase in {RunPhase.FAILED, RunPhase.CANCELLED}:
            self.emit("run.failed", terminal)
        else:
            self.emit("run.completed", terminal)
        if resumable:
            persist_phase = RunPhase.WORKING if phase is RunPhase.STOPPED else phase
            self.store.finish_run(
                self.run_id,
                phase=persist_phase,
                stop_reason=stop_reason,
                status="stopped",
            )
            return
        status = "active" if phase is RunPhase.WORKING else "finished"
        if phase in {RunPhase.STOPPED, RunPhase.FAILED, RunPhase.CANCELLED}:
            status = "stopped"
        self.store.finish_run(self.run_id, phase=phase, stop_reason=stop_reason, status=status)

    def record_approval_for_call(self, call: ToolCall, status: str) -> None:
        self.store.record_approval(
            self.run_id,
            uuid.uuid4().hex,
            args_hash_for_tool(call.args),
            status,
            resolved=status in {"approved", "denied", "used"},
        )


class ToolTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
