from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import Field

from codeagent.plan.render import format_plan_for_context
from codeagent.state.store import PlanItemRecord, StateStore
from codeagent.tools.base import StrictArgs, ToolResult


class PlanItemInput(StrictArgs):
    text: str
    status: Literal["pending", "in_progress", "done", "blocked"]
    depends_on: list[int] = Field(default_factory=list)


class UpdatePlanArgs(StrictArgs):
    items: list[PlanItemInput]


def handle_update_plan(
    args: UpdatePlanArgs,
    *,
    store: StateStore,
    run_id: str,
    on_updated: Callable[[str], None] | None = None,
) -> ToolResult:
    records = [
        PlanItemRecord(
            idx=i,
            text=item.text,
            status=item.status,
            depends_on=list(item.depends_on),
            attempt=0,
            max_attempts=3,
        )
        for i, item in enumerate(args.items)
    ]
    store.replace_plan_items(run_id, records)
    rendered = format_plan_for_context(records)
    if on_updated:
        on_updated(rendered)
    return ToolResult(ok=True, summary="plan updated", content=rendered, truncated=False)
