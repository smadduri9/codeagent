"""Agent tool-call loop (skeleton)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from codeagent.lifecycle import LifecycleState, RunPhase
from codeagent.loop.guards import LoopGuards
from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelRequest,
    StopReason,
    ToolCall,
)
from codeagent.providers.protocol import Provider
from codeagent.providers.stream import collect_stream
from codeagent.tools.registry import ToolRegistry, ToolValidationError, UnknownToolError
from codeagent.tools.truncate import truncate_content


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class RunResult:
    stop_reason: str
    iterations: int
    history: list[Message] = field(default_factory=list)
    guard_warning: str | None = None


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
) -> RunResult:
    lifecycle = LifecycleState()
    lifecycle.transition(RunPhase.WORKING)
    guards = LoopGuards(max_iterations=max_iterations)
    history: list[Message] = [Message(role=MessageRole.USER, content=goal)]
    permission = decide or (lambda _call: PermissionDecision.ALLOW)
    guard_warning: str | None = None

    while True:
        guard = guards.on_iteration_start()
        if guard.stop:
            lifecycle.transition(RunPhase.STOPPED)
            return RunResult(
                stop_reason=guard.reason.value if guard.reason else "stopped",
                iterations=guards.state.iterations,
                history=history,
                guard_warning=guard_warning,
            )

        request = ModelRequest(
            system=system,
            messages=history,
            tools=registry.list_specs(),
            model=model,
            max_output_tokens=max_output_tokens,
        )
        reply = collect_stream(provider.stream(request))
        assistant = Message(
            role=MessageRole.ASSISTANT,
            content=reply.content or None,
            tool_calls=reply.tool_calls,
        )
        history.append(assistant)

        if not reply.tool_calls:
            lifecycle.transition(RunPhase.COMPLETED)
            reason = reply.stop_reason.value if reply.stop_reason else StopReason.STOP.value
            return RunResult(
                stop_reason=reason,
                iterations=guards.state.iterations,
                history=history,
                guard_warning=guard_warning,
            )

        tool_messages: list[Message] = []
        for call in reply.tool_calls:
            repeat = guards.on_tool_call(call)
            if repeat.warning and guard_warning is None:
                guard_warning = repeat.warning
            if repeat.stop:
                lifecycle.transition(RunPhase.STOPPED)
                return RunResult(
                    stop_reason=repeat.reason.value if repeat.reason else "stopped",
                    iterations=guards.state.iterations,
                    history=history,
                    guard_warning=guard_warning,
                )

            decision = permission(call)
            if decision is PermissionDecision.DENY:
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
                    lifecycle.transition(RunPhase.STOPPED)
                    return RunResult(
                        stop_reason=denial.reason.value if denial.reason else "stopped",
                        iterations=guards.state.iterations,
                        history=history + tool_messages,
                        guard_warning=guard_warning,
                    )
                continue

            guards.on_allow()
            try:
                result = registry.run(call)
            except (ToolValidationError, UnknownToolError) as exc:
                result = registry.tool_error(call, str(exc))
            body, _truncated = truncate_content(result.content, max_output_chars, keep="tail")
            tool_messages.append(
                Message(
                    role=MessageRole.TOOL,
                    content=body,
                    tool_call_id=call.id,
                    name=call.name,
                ),
            )
        history.extend(tool_messages)
