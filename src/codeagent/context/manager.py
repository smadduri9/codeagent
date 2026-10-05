"""Assemble model context with a stable prefix."""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps

from codeagent.config import Settings
from codeagent.context.compaction import CompactionResult, CompactionState, compact_history
from codeagent.context.prompts import load_system_prompt, prompt_hash
from codeagent.context.tokens import (
    estimate_messages_tokens,
    estimate_text_tokens,
    estimate_tool_specs_tokens,
)
from codeagent.providers.base import Message, MessageRole
from codeagent.tools.base import ToolSpec


@dataclass(frozen=True)
class AssembledContext:
    system: str
    messages: list[Message]
    tools: list[ToolSpec]
    stable_prefix_hash: str
    prompt_hash: str
    estimated_input_tokens: int
    compaction: CompactionResult | None = None


@dataclass
class ContextManager:
    settings: Settings
    instructions: str
    compaction_state: CompactionState | None = None

    def stable_prefix_bytes(self, tools: list[ToolSpec]) -> bytes:
        system = load_system_prompt()
        payload = (
            system
            + "\n"
            + dumps(
                [tool.model_dump() for tool in tools],
                sort_keys=True,
            )
        )
        payload += "\n" + self.instructions
        return payload.encode("utf-8")

    def render_plan_message(self, plan_text: str) -> Message | None:
        if not plan_text.strip():
            return None
        return Message(role=MessageRole.USER, content=f"[plan]\n{plan_text}")

    def assemble(
        self,
        *,
        goal: str,
        history: list[Message],
        tools: list[ToolSpec],
        plan_text: str = "",
        summarize: str | None = None,
    ) -> AssembledContext:
        state = self.compaction_state or CompactionState()
        compaction = compact_history(
            history,
            goal=goal,
            request=self.settings.request,
            context=self.settings.context,
            state=state,
            summarize=summarize,
        )
        working_history = list(compaction.history)
        plan_message = self.render_plan_message(plan_text)
        messages = list(working_history)
        if plan_message is not None:
            messages.append(plan_message)

        system = load_system_prompt()
        if self.instructions:
            system = f"{system}\n\n# Repository instructions\n\n{self.instructions}"

        prefix_hash = prompt_hash(self.stable_prefix_bytes(tools).decode("utf-8"))
        full_prompt_hash = prompt_hash(system + prefix_hash + plan_text)
        estimated = (
            estimate_text_tokens(system)
            + estimate_tool_specs_tokens(tools)
            + estimate_messages_tokens(messages)
        )
        self.compaction_state = compaction.state
        return AssembledContext(
            system=system,
            messages=messages,
            tools=tools,
            stable_prefix_hash=prefix_hash,
            prompt_hash=full_prompt_hash,
            estimated_input_tokens=estimated,
            compaction=compaction if compaction.compacted else None,
        )

    def needs_compaction_before_request(
        self,
        *,
        goal: str,
        history: list[Message],
        tools: list[ToolSpec],
    ) -> bool:
        assembled = self.assemble(goal=goal, history=history, tools=tools)
        return assembled.estimated_input_tokens > self.settings.request.max_request_tokens
