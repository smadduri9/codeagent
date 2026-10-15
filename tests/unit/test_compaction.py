from codeagent.config import ContextSettings, RequestSettings, Settings
from codeagent.context.compaction import CompactionState, compact_history, summarize_prefix
from codeagent.providers.base import Message, MessageRole, ToolCall


def test_third_compaction_handoff() -> None:
    goal = "big task"
    huge = Message(role=MessageRole.TOOL, content="y" * 8000, name="grep", tool_call_id="2")
    history = [Message(role=MessageRole.USER, content=goal), huge]
    settings = Settings(
        request=RequestSettings(max_request_tokens=50),
        context=ContextSettings(max_summaries=2),
    )
    result = compact_history(
        history,
        goal=goal,
        request=settings.request,
        context=settings.context,
        state=CompactionState(summary_count=2),
    )
    assert result.action == "handoff"


def _exchange(i: int) -> list[Message]:
    call = ToolCall(id=f"c{i}", name="read_file", args={"path": f"f{i}.py"})
    return [
        Message(role=MessageRole.ASSISTANT, content=None, tool_calls=[call]),
        Message(role=MessageRole.TOOL, content=f"out{i}", tool_call_id=f"c{i}", name="read_file"),
    ]


def test_summarize_never_keeps_a_tool_result_without_its_call() -> None:
    history = [Message(role=MessageRole.USER, content="the goal")]
    for i in range(4):
        history += _exchange(i)
    # keep_turns=3 would start the tail on the TOOL message of exchange 2
    out = summarize_prefix(history, keep_turns=3, summary_text="[summary 1] s")
    first_kept = out[2]
    assert first_kept.role is MessageRole.ASSISTANT
    ids_with_calls = {c.id for m in out for c in m.tool_calls}
    assert all(m.tool_call_id in ids_with_calls for m in out if m.role is MessageRole.TOOL)


def test_summarize_keeps_the_original_goal() -> None:
    history = [Message(role=MessageRole.USER, content="the goal")]
    for i in range(4):
        history += _exchange(i)
    out = summarize_prefix(history, keep_turns=2, summary_text="[summary 1] s")
    assert out[0].content == "the goal"
    assert out[1].content == "[summary 1] s"
