"""Render persisted plan rows for model context."""

from __future__ import annotations

from codeagent.state.store import PlanItemRecord


def order_plan_items(items: list[PlanItemRecord]) -> list[PlanItemRecord]:
    by_idx = {item.idx: item for item in items}
    ordered: list[PlanItemRecord] = []
    seen: set[int] = set()

    def visit(idx: int) -> None:
        if idx in seen:
            return
        item = by_idx.get(idx)
        if item is None:
            return
        for dep in item.depends_on:
            visit(dep)
        seen.add(idx)
        ordered.append(item)

    for item in sorted(items, key=lambda row: row.idx):
        visit(item.idx)
    return ordered


def format_plan_for_context(items: list[PlanItemRecord]) -> str:
    if not items:
        return ""
    lines = [
        f"{item.idx}. [{item.status}] {item.text}"
        + (f" (depends on {','.join(str(d) for d in item.depends_on)})" if item.depends_on else "")
        for item in order_plan_items(items)
    ]
    return "\n".join(lines)
