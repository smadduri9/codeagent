from codeagent.config import ContextSettings, RequestSettings, Settings
from codeagent.context.compaction import CompactionState, compact_history
from codeagent.providers.base import Message, MessageRole


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
