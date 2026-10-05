"""Apply DESIGN 9.1 gate heuristics to live eval metrics."""

from __future__ import annotations

from dataclasses import dataclass

from evals.live_agent import LiveTaskMetrics


@dataclass(frozen=True)
class GateAssessment:
    passed: bool
    conclusion: str
    search_share_failed: float
    tasks_run: int
    tasks_passed: int


def assess_gate(results: list[LiveTaskMetrics]) -> GateAssessment:
    if not results:
        return GateAssessment(
            passed=False,
            conclusion="Undetermined — no live tasks completed.",
            search_share_failed=0.0,
            tasks_run=0,
            tasks_passed=0,
        )
    failed = [row for row in results if not row.ok]
    tasks_passed = sum(1 for row in results if row.ok)
    search_share = 0.0
    if failed:
        model_calls = sum(max(1, row.model_calls) for row in failed)
        search_calls = sum(row.search_calls for row in failed)
        search_share = search_calls / model_calls
    passed = search_share > 0.30 and len(failed) > 0
    if passed:
        conclusion = "Gate met — repository intelligence may proceed."
    elif len(results) < 12:
        conclusion = (
            "Undetermined — partial core12 slice; "
            f"search share on failed tasks={search_share:.2f} (need >0.30 on failures)."
        )
    else:
        conclusion = (
            f"Gate not met — search share on failed tasks={search_share:.2f} (threshold 0.30)."
        )
    return GateAssessment(
        passed=passed,
        conclusion=conclusion,
        search_share_failed=search_share,
        tasks_run=len(results),
        tasks_passed=tasks_passed,
    )
