"""Gate assessment tests."""

from evals.gate_analysis import assess_gate
from evals.live_agent import LiveTaskMetrics


def test_gate_not_met_without_failures() -> None:
    assessment = assess_gate(
        [
            LiveTaskMetrics(
                "t1",
                ok=True,
                model_calls=3,
                search_calls=2,
                total_tool_calls=2,
                tokens=10,
            ),
        ],
    )
    assert not assessment.passed


def test_gate_met_when_search_heavy_on_failures() -> None:
    assessment = assess_gate(
        [
            LiveTaskMetrics(
                "t1",
                ok=False,
                model_calls=2,
                search_calls=2,
                total_tool_calls=2,
                tokens=5,
            ),
        ],
    )
    assert assessment.passed
