"""History compaction: prune, summarize, handoff."""

from __future__ import annotations

from dataclasses import dataclass, field
from json import dumps

from codeagent.config import ContextSettings, RequestSettings
from codeagent.context.tokens import estimate_messages_tokens
from codeagent.providers.base import Message, MessageRole


@dataclass
class CompactionState:
    summary_count: int = 0
    handoff: str | None = None


@dataclass
class CompactionResult:
    history: list[Message]
    compacted: bool
    action: str | None = None
    state: CompactionState = field(default_factory=CompactionState)


def _is_protected(message: Message, *, goal: str) -> bool:
    if message.role is MessageRole.USER:
        return True
    if message.content and goal and message.content.strip() == goal.strip():
        return True
    if message.content and message.content.startswith("[plan]"):
        return True
    if message.content and message.content.startswith("[verification]"):
        return True
    if message.content and message.content.startswith("[failure]"):
        return True
    return False


def _stub_tool_message(message: Message) -> Message:
    name = message.name or "tool"
    preview = (message.content or "")[:120]
    return Message(
        role=MessageRole.TOOL,
        content=f"[output of {name} elided; re-run if needed; was: {preview!r}]",
        tool_call_id=message.tool_call_id,
        name=message.name,
    )


def prune_tool_results(
    history: list[Message],
    *,
    keep: int,
    goal: str,
) -> list[Message]:
    tool_indices = [
        index
        for index, message in enumerate(history)
        if message.role is MessageRole.TOOL and not _is_protected(message, goal=goal)
    ]
    if len(tool_indices) <= keep:
        return list(history)
    drop = set(tool_indices[:-keep])
    pruned: list[Message] = []
    for index, message in enumerate(history):
        if index in drop:
            pruned.append(_stub_tool_message(message))
        else:
            pruned.append(message)
    return pruned


def summarize_prefix(
    history: list[Message],
    *,
    keep_turns: int,
    summary_text: str,
) -> list[Message]:
    if keep_turns <= 0:
        return [Message(role=MessageRole.USER, content=summary_text), *history]
    tail_start = max(0, len(history) - keep_turns)
    tail = history[tail_start:]
    return [Message(role=MessageRole.USER, content=summary_text), *tail]


def build_handoff_summary(*, goal: str, history: list[Message]) -> str:
    paths: list[str] = []
    for message in history:
        if message.content and ".py:" in message.content:
            paths.append(message.content.split("\n", 1)[0][:120])
    return (
        "Handoff summary:\n"
        f"- Goal: {goal}\n"
        f"- Decisions: continued work in-session ({len(history)} messages)\n"
        f"- Current state: context limit reached after compaction\n"
        f"- Next step: resume with a narrower goal or fresh run\n"
        f"- Paths noted: {dumps(paths[:5])}"
    )


def compact_history(
    history: list[Message],
    *,
    goal: str,
    request: RequestSettings,
    context: ContextSettings,
    state: CompactionState,
    summarize: str | None = None,
) -> CompactionResult:
    """Prune then optionally summarize; third compaction becomes handoff."""
    estimated = estimate_messages_tokens(history)
    if estimated <= request.max_request_tokens:
        return CompactionResult(history=list(history), compacted=False, state=state)

    if state.summary_count >= context.max_summaries:
        handoff = build_handoff_summary(goal=goal, history=history)
        new_state = CompactionState(summary_count=state.summary_count, handoff=handoff)
        return CompactionResult(
            history=history,
            compacted=True,
            action="handoff",
            state=new_state,
        )

    pruned = prune_tool_results(
        history,
        keep=context.prune_keep_tool_results,
        goal=goal,
    )
    if estimate_messages_tokens(pruned) <= request.max_request_tokens:
        return CompactionResult(history=pruned, compacted=True, action="prune", state=state)

    summary_body = summarize or (
        "Earlier conversation summarized: goal preserved, tool outputs pruned, "
        "recent turns kept verbatim."
    )
    summarized = summarize_prefix(
        pruned,
        keep_turns=context.summarize_keep_turns,
        summary_text=f"[summary {state.summary_count + 1}] {summary_body}",
    )
    new_state = CompactionState(summary_count=state.summary_count + 1)
    return CompactionResult(
        history=summarized,
        compacted=True,
        action="summarize",
        state=new_state,
    )
