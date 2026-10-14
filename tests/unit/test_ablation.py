"""Paired ablation report over two arms of eval results."""

from evals.ablation import compare_arms, render_markdown
from evals.runner import EvalResult


def _row(task: str, ok: bool, tokens: int = 100, repeat: int = 0) -> EvalResult:
    return EvalResult(task_id=task, ok=ok, mode="replay", tokens=tokens, repeat=repeat)


def test_paired_counts_and_mcnemar_p_value() -> None:
    on = [_row(f"t{i}", True) for i in range(10)]
    off = [_row(f"t{i}", i < 2) for i in range(10)]
    report = compare_arms("on", on, "off", off)
    assert report.on.passed == 10 and report.off.passed == 2
    assert report.only_on == 8 and report.only_off == 0
    # Two-sided exact McNemar with b=8, c=0: 2 * (1 + 8 + 28 + ...)/... = 2 / 2**8
    assert abs(report.mcnemar_p - 2 / 256) < 1e-12


def test_majority_of_repeats_decides_a_task() -> None:
    rows = [_row("t1", True, repeat=0), _row("t1", True, repeat=1), _row("t1", False, repeat=2)]
    report = compare_arms("on", rows, "off", [_row("t1", False)])
    assert report.on.passed == 1


def test_tokens_per_solved_task_sums_repeats() -> None:
    rows = [_row("t1", True, tokens=50, repeat=0), _row("t1", True, tokens=70, repeat=1)]
    report = compare_arms("on", rows, "off", [_row("t1", False, tokens=10)])
    assert report.on.tokens_median == 120.0


def test_markdown_has_both_arms_and_p_value() -> None:
    on = [_row("t1", True)]
    off = [_row("t1", False)]
    text = render_markdown(compare_arms("on", on, "off", off), model="m", flag="compaction")
    assert "| on |" in text and "| off |" in text
    assert "McNemar" in text
