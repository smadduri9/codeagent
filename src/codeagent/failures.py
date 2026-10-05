from __future__ import annotations

from enum import StrEnum

from codeagent.providers.base import ToolCall
from codeagent.state.store import StateStore, args_hash_for_tool


class FailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    ENVIRONMENT = "ENVIRONMENT"
    TEST_FAILURE = "TEST_FAILURE"
    PATCH_CONFLICT = "PATCH_CONFLICT"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    INVALID_PLAN = "INVALID_PLAN"
    POLICY_BLOCK = "POLICY_BLOCK"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    UNRECOVERABLE = "UNRECOVERABLE"


def classify_tool_failure(tool: str, message: str) -> FailureClass:
    lowered = message.lower()
    if "denied" in lowered or "policy" in lowered:
        return FailureClass.POLICY_BLOCK
    if "not found" in lowered or "missing" in lowered:
        return FailureClass.MISSING_CONTEXT
    if tool in {"run_verification", "run_tests"}:
        return FailureClass.TEST_FAILURE
    return FailureClass.UNRECOVERABLE


def change_approach_message(failure: FailureClass, detail: str) -> str:
    return f"Change approach: {failure.value} — {detail}."


class IdenticalRetryGuard:
    def __init__(self) -> None:
        self._last: str | None = None
        self._count = 0

    def check(self, call: ToolCall) -> str | None:
        digest = f"{call.name}:{args_hash_for_tool(call.args)}"
        if digest == self._last:
            self._count += 1
            if self._count >= 2:
                return "Identical retry refused without new evidence."
        else:
            self._last = digest
            self._count = 0
        return None


class AttemptLimiter:
    def __init__(self, store: StateStore, run_id: str, max_attempts: int = 3) -> None:
        self._store = store
        self._run_id = run_id
        self._max_attempts = max_attempts
        self._reconsider_used = False

    @property
    def reconsider_used(self) -> bool:
        return self._reconsider_used

    def record_failure(self) -> str | None:
        idx = next(
            (
                item.idx
                for item in self._store.list_plan_items(self._run_id)
                if item.status == "in_progress"
            ),
            None,
        )
        if idx is None:
            return None
        attempts = self._store.increment_plan_attempt(self._run_id, idx)
        if attempts < self._max_attempts:
            return None
        if not self._reconsider_used:
            self._reconsider_used = True
            return "Stop and reconsider the approach."
        return "Stopping after repeated verification failures."
