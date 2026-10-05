"""Rebuild conversation history from persisted steps and tool calls."""

from __future__ import annotations

import json
import sqlite3

from codeagent.providers.base import Message, MessageRole
from codeagent.state.store import StateStore


def rebuild_history(store: StateStore, run_id: str) -> list[Message]:
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"unknown run: {run_id}")

    history: list[Message] = [Message(role=MessageRole.USER, content=run.goal)]
    steps = store.list_steps(run_id)
    tool_rows = store.list_tool_calls(run_id)
    tools_by_step: dict[int, list[sqlite3.Row]] = {}
    for row in tool_rows:
        tools_by_step.setdefault(int(row["step_id"]), []).append(row)

    for step in steps:
        assistant = Message.model_validate_json(step["assistant_json"])
        history.append(assistant)
        step_id = int(step["id"])
        for index, tool_row in enumerate(tools_by_step.get(step_id, [])):
            if tool_row["ok"] is None:
                continue
            payload = json.loads(tool_row["result_json"] or "{}")
            content = payload.get("content", "")
            call_id = (
                assistant.tool_calls[index].id
                if index < len(assistant.tool_calls)
                else f"tool-{tool_row['id']}"
            )
            history.append(
                Message(
                    role=MessageRole.TOOL,
                    content=str(content),
                    tool_call_id=call_id,
                    name=tool_row["tool"],
                ),
            )
    return history
