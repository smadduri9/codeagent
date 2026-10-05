"""Agent tool-call loop."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from codeagent.lifecycle import LifecycleState, RunPhase
from codeagent.loop.budget import (
    BudgetTracker,
    ExhaustionReport,
    build_exhaustion_report,
)
from codeagent.loop.completion_gate import CompletionGate, GateAction
from codeagent.loop.guards import LoopGuards
from codeagent.loop.interrupt import InterruptController
from codeagent.loop.limits import RunLimits
from codeagent.loop.observers import NullRunOutputObserver, RunOutputObserver
from codeagent.loop.policy import PolicyGate
from codeagent.permissions.types import is_allow
from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelRequest,
    StopReason,
    ToolCall,
)
from codeagent.providers.protocol import Provider
from codeagent.providers.stream import collect_stream
from codeagent.state.recorder import RunRecorder, ToolTimer
from codeagent.state.store import StateStore
from codeagent.tools.registry import ToolRegistry, ToolValidationError, UnknownToolError
from codeagent.tools.truncate import truncate_content


class PermissionDecision(StrEnum):
    """Legacy coarse decision for simple loop tests."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass
class RunResult:
    stop_reason: str
    iterations: int
    history: list[Message] = field(default_factory=list)
    guard_warning: str | None = None
    policy: PolicyGate | None = None
    run_id: str | None = None
    exhaustion_report: ExhaustionReport | None = None
    resume_warnings: list[str] = field(default_factory=list)


def run_agent_loop(
    goal: str,
    provider: Provider,
    registry: ToolRegistry,
    *,
    max_iterations: int,
    max_output_chars: int = 8000,
    system: str = "You are a coding agent.",
    model: str = "test-model",
    max_output_tokens: int = 256,
    decide: Callable[[ToolCall], PermissionDecision] | None = None,
    policy: PolicyGate | None = None,
    completion_gate: CompletionGate | None = None,
    store: StateStore | None = None,
    run_id: str | None = None,
    repo_root: Path | None = None,
    history: list[Message] | None = None,
    lifecycle: LifecycleState | None = None,
    recorder: RunRecorder | None = None,
    limits: RunLimits | None = None,
    budget: BudgetTracker | None = None,
    interrupt: InterruptController | None = None,
    resume_warnings: list[str] | None = None,
    output: RunOutputObserver | None = None,
) -> RunResult:
    del store, repo_root
    lifecycle_state = lifecycle or LifecycleState()
    if lifecycle_state.phase is RunPhase.INITIALIZING:
        lifecycle_state.transition(RunPhase.WORKING)
        if recorder is not None:
            recorder.on_phase(RunPhase.WORKING)

    if limits is not None and budget is None:
        budget = BudgetTracker(limits=limits)

    guards = LoopGuards(max_iterations=max_iterations)
    chat_history: list[Message] = (
        list(history) if history is not None else [Message(role=MessageRole.USER, content=goal)]
    )
    legacy_decide = decide or (lambda _call: PermissionDecision.ALLOW)
    guard_warning: str | None = None
    warnings = list(resume_warnings or [])
    changed_files: list[str] = []
    gate = completion_gate or CompletionGate()
    sink = output if output is not None else NullRunOutputObserver()

    if policy is not None and recorder is not None:
        policy.on_record = recorder.on_decision

    def _finish(
        phase: RunPhase,
        stop_reason: str,
        *,
        exhaustion: bool = False,
        resumable: bool = False,
    ) -> RunResult:
        exhaustion_report: ExhaustionReport | None = None
        if exhaustion:
            exhaustion_report = build_exhaustion_report(
                goal=goal,
                stop_reason=stop_reason,
                iterations=guards.state.iterations,
                tool_calls=budget.tool_calls if budget is not None else 0,
                changed_files=changed_files,
            )
        if recorder is not None:
            recorder.on_phase(phase)
            recorder.finish(phase, stop_reason, resumable=resumable)
        return RunResult(
            stop_reason=stop_reason,
            iterations=guards.state.iterations,
            history=chat_history,
            guard_warning=guard_warning,
            policy=policy,
            run_id=run_id,
            exhaustion_report=exhaustion_report,
            resume_warnings=warnings,
        )

    while True:
        guard = guards.on_iteration_start()
        if guard.stop:
            lifecycle_state.transition(RunPhase.STOPPED)
            return _finish(
                RunPhase.STOPPED,
                guard.reason.value if guard.reason else "stopped",
            )

        if budget is not None:
            budget_guard = budget.check()
            if budget_guard.stop:
                lifecycle_state.transition(RunPhase.STOPPED)
                return _finish(
                    RunPhase.STOPPED,
                    budget_guard.reason.value if budget_guard.reason else "budget_exhausted",
                    exhaustion=True,
                    resumable=True,
                )

        iteration = guards.state.iterations
        if recorder is not None:
            recorder.emit(
                "model.request",
                {
                    "iteration": iteration,
                    "model": model,
                    "message_count": len(chat_history),
                },
            )

        request = ModelRequest(
            system=system,
            messages=chat_history,
            tools=registry.list_specs(),
            model=model,
            max_output_tokens=max_output_tokens,
        )
        started = time.perf_counter()
        reply = collect_stream(
            provider.stream(request),
            on_text_delta=sink.on_text_delta,
            on_tool_announced=sink.on_tool_announced,
        )
        sink.on_model_turn_end()
        latency_ms = int((time.perf_counter() - started) * 1000)

        if recorder is not None:
            usage = reply.usage
            recorder.emit(
                "model.response",
                {
                    "iteration": iteration,
                    "stop_reason": reply.stop_reason.value if reply.stop_reason else None,
                    "tool_calls": len(reply.tool_calls),
                    "tokens_in": usage.input if usage else 0,
                    "tokens_out": usage.output if usage else 0,
                    "latency_ms": latency_ms,
                },
            )

        if budget is not None and reply.usage is not None:
            budget.add_usage(reply.usage)
            budget_guard = budget.check()
            if budget_guard.stop:
                lifecycle_state.transition(RunPhase.STOPPED)
                return _finish(
                    RunPhase.STOPPED,
                    budget_guard.reason.value if budget_guard.reason else "budget_exhausted",
                    exhaustion=True,
                    resumable=True,
                )

        assistant = Message(
            role=MessageRole.ASSISTANT,
            content=reply.content or None,
            tool_calls=reply.tool_calls,
        )
        chat_history.append(assistant)

        step_cost = budget.cost_usd if budget is not None else 0.0
        if recorder is not None:
            recorder.on_assistant_step(
                assistant,
                reply.usage,
                cost_usd=step_cost,
                latency_ms=latency_ms,
            )

        if interrupt is not None and interrupt.should_stop_after_model():
            interrupt.clear_graceful()
            lifecycle_state.transition(RunPhase.STOPPED)
            return _finish(RunPhase.STOPPED, "interrupt", exhaustion=True, resumable=True)

        if not reply.tool_calls:
            action = gate.on_model_stop()
            if action is GateAction.PROMPT_VERIFY:
                chat_history.append(
                    Message(role=MessageRole.USER, content=CompletionGate.prompt_message())
                )
                continue
            if action is GateAction.COMPLETE_UNVERIFIED:
                lifecycle_state.transition(RunPhase.COMPLETED_UNVERIFIED)
                return _finish(RunPhase.COMPLETED_UNVERIFIED, "completed_unverified")
            lifecycle_state.transition(RunPhase.COMPLETED)
            reason = reply.stop_reason.value if reply.stop_reason else StopReason.STOP.value
            return _finish(RunPhase.COMPLETED, reason)

        tool_messages: list[Message] = []
        for call in reply.tool_calls:
            if recorder is not None:
                recorder.emit(
                    "tool.requested",
                    {
                        "iteration": iteration,
                        "tool": call.name,
                        "call_id": call.id,
                    },
                )
            repeat = guards.on_tool_call(call)
            if repeat.warning and guard_warning is None:
                guard_warning = repeat.warning
            if repeat.stop:
                lifecycle_state.transition(RunPhase.STOPPED)
                return _finish(
                    RunPhase.STOPPED,
                    repeat.reason.value if repeat.reason else "stopped",
                )

            if policy is not None:
                decision, deny_message = policy.evaluate(call)
                if not is_allow(decision):
                    denial = guards.on_denial()
                    content = policy.wrap_result(
                        policy.denied_result(
                            call,
                            deny_message or "denied",
                        ),
                    )
                    if recorder is not None:
                        recorder.complete_tool(
                            call,
                            ok=False,
                            result_content=content,
                            duration_ms=0,
                        )
                    tool_messages.append(
                        Message(
                            role=MessageRole.TOOL,
                            content=content,
                            tool_call_id=call.id,
                            name=call.name,
                        ),
                    )
                    if denial.stop:
                        lifecycle_state.transition(RunPhase.STOPPED)
                        chat_history.extend(tool_messages)
                        return _finish(
                            RunPhase.STOPPED,
                            denial.reason.value if denial.reason else "stopped",
                        )
                    continue

                if interrupt is not None and interrupt.should_stop_before_tool():
                    lifecycle_state.transition(RunPhase.STOPPED)
                    return _finish(
                        RunPhase.STOPPED,
                        "interrupt",
                        exhaustion=True,
                        resumable=True,
                    )

                guards.on_allow()
                if recorder is not None:
                    recorder.emit(
                        "tool.started",
                        {"tool": call.name, "call_id": call.id},
                    )
                sink.on_tool_start(call.name)
                timer = ToolTimer()
                result = policy.execute_allowed(call, decision)
                sink.on_tool_end(call.name, result.ok)
                body, _truncated = truncate_content(
                    policy.wrap_result(result),
                    max_output_chars,
                    keep="tail",
                )
                if recorder is not None:
                    recorder.complete_tool(
                        call,
                        ok=result.ok,
                        result_content=body,
                        duration_ms=timer.elapsed_ms(),
                    )
                if budget is not None:
                    budget.on_tool_completed()
                tool_messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=body,
                        tool_call_id=call.id,
                        name=call.name,
                    ),
                )
                if interrupt is not None and (
                    interrupt.should_stop_after_current_tool()
                    or interrupt.should_stop_before_tool()
                ):
                    interrupt.clear_graceful()
                    lifecycle_state.transition(RunPhase.STOPPED)
                    chat_history.extend(tool_messages)
                    return _finish(
                        RunPhase.STOPPED,
                        "interrupt",
                        exhaustion=True,
                        resumable=True,
                    )
                continue

            legacy = legacy_decide(call)
            if legacy is PermissionDecision.DENY:
                if recorder is not None:
                    recorder.record_legacy_decision(call, allowed=False)
                    recorder.complete_tool(
                        call,
                        ok=False,
                        result_content=f"denied: {call.name}",
                        duration_ms=0,
                    )
                denial = guards.on_denial()
                content = f"denied: {call.name}"
                tool_messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=content,
                        tool_call_id=call.id,
                        name=call.name,
                    ),
                )
                if denial.stop:
                    lifecycle_state.transition(RunPhase.STOPPED)
                    chat_history.extend(tool_messages)
                    return _finish(
                        RunPhase.STOPPED,
                        denial.reason.value if denial.reason else "stopped",
                    )
                continue

            if recorder is not None:
                recorder.record_legacy_decision(call, allowed=True)

            if interrupt is not None and interrupt.should_stop_before_tool():
                lifecycle_state.transition(RunPhase.STOPPED)
                return _finish(
                    RunPhase.STOPPED,
                    "interrupt",
                    exhaustion=True,
                    resumable=True,
                )

            guards.on_allow()
            if recorder is not None:
                recorder.emit(
                    "tool.started",
                    {"tool": call.name, "call_id": call.id},
                )
            sink.on_tool_start(call.name)
            timer = ToolTimer()
            try:
                result = registry.run(call)
            except (ToolValidationError, UnknownToolError) as exc:
                result = registry.tool_error(call, str(exc))
            sink.on_tool_end(call.name, result.ok)
            if call.name in {"write_file", "edit_file"} and result.ok:
                gate.note_edit()
                path_arg = call.args.get("path")
                if isinstance(path_arg, str):
                    changed_files.append(path_arg)
            if call.name in {"run_verification", "run_tests"} and result.ok:
                gate.note_verification_pass()
            body, _truncated = truncate_content(result.content, max_output_chars, keep="tail")
            if recorder is not None:
                recorder.complete_tool(
                    call,
                    ok=result.ok,
                    result_content=body,
                    duration_ms=timer.elapsed_ms(),
                )
            if budget is not None:
                budget.on_tool_completed()
            tool_messages.append(
                Message(
                    role=MessageRole.TOOL,
                    content=body,
                    tool_call_id=call.id,
                    name=call.name,
                ),
            )
            if interrupt is not None and (
                interrupt.should_stop_after_current_tool() or interrupt.should_stop_before_tool()
            ):
                interrupt.clear_graceful()
                lifecycle_state.transition(RunPhase.STOPPED)
                chat_history.extend(tool_messages)
                return _finish(
                    RunPhase.STOPPED,
                    "interrupt",
                    exhaustion=True,
                    resumable=True,
                )

        chat_history.extend(tool_messages)
