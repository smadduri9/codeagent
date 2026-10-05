from codeagent.config import Settings
from codeagent.context import ContextManager, load_instructions
from codeagent.context.prompts import load_system_prompt
from codeagent.context.tokens import estimate_text_tokens, estimate_tool_specs_tokens
from codeagent.providers.base import Message, MessageRole
from codeagent.tools.registry import ToolRegistry


def test_prefix_hash_stable_when_plan_changes(tmp_path) -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path)
    tools = registry.list_specs()
    manager = ContextManager(settings=Settings(), instructions="")
    first = manager.assemble(
        goal="fix bug",
        history=[Message(role=MessageRole.USER, content="fix bug")],
        tools=tools,
        plan_text="step one",
    )
    second = manager.assemble(
        goal="fix bug",
        history=[Message(role=MessageRole.USER, content="fix bug")],
        tools=tools,
        plan_text="step two",
    )
    assert first.stable_prefix_hash == second.stable_prefix_hash
    assert first.prompt_hash != second.prompt_hash


def test_instructions_load_order_and_cap(tmp_path) -> None:
    (tmp_path / "CODEAGENT.md").write_text("codeagent\n", encoding="utf-8")
    loaded = load_instructions(tmp_path, max_tokens=2)
    assert "CODEAGENT.md" in loaded.sources


def test_system_prompt_under_budget(tmp_path) -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path)
    tools = registry.list_specs()
    system = load_system_prompt()
    total = estimate_text_tokens(system) + estimate_tool_specs_tokens(tools)
    assert total <= 3000
