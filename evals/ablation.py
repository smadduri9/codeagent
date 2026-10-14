"""Paired ablation report: compare two arms of eval results with exact statistics.

A task passes in an arm when most of its repeats pass (ties count as failing).
Pure functions; reads no files and makes no model calls.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from evals.runner import EvalResult
from evals.stats import mcnemar_exact, median_p90, wilson_interval


@dataclass(frozen=True)
class ArmSummary:
    name: str
    total: int
    passed: int
    pass_rate: float
    ci_low: float
    ci_high: float
    tokens_median: float
    tokens_p90: float


@dataclass(frozen=True)
class AblationReport:
    on: ArmSummary
    off: ArmSummary
    only_on: int
    only_off: int
    mcnemar_p: float


def _task_outcomes(rows: list[EvalResult]) -> dict[str, bool]:
    grouped: dict[str, list[EvalResult]] = defaultdict(list)
    for row in rows:
        grouped[row.task_id].append(row)
    return {task: sum(r.ok for r in runs) * 2 > len(runs) for task, runs in grouped.items()}


def _summarise(name: str, rows: list[EvalResult], outcomes: dict[str, bool]) -> ArmSummary:
    total = len(outcomes)
    passed = sum(outcomes.values())
    low, high = wilson_interval(passed, total) if total else (0.0, 0.0)
    solved_tokens: dict[str, int] = defaultdict(int)
    for row in rows:
        if outcomes.get(row.task_id):
            solved_tokens[row.task_id] += row.tokens
    if solved_tokens:
        median, p90 = median_p90([float(v) for v in solved_tokens.values()])
    else:
        median, p90 = 0.0, 0.0
    return ArmSummary(
        name=name,
        total=total,
        passed=passed,
        pass_rate=passed / total if total else 0.0,
        ci_low=low,
        ci_high=high,
        tokens_median=median,
        tokens_p90=p90,
    )


def compare_arms(
    on_name: str,
    on_rows: list[EvalResult],
    off_name: str,
    off_rows: list[EvalResult],
) -> AblationReport:
    on_out = _task_outcomes(on_rows)
    off_out = _task_outcomes(off_rows)
    shared = sorted(set(on_out) & set(off_out))
    only_on = sum(1 for t in shared if on_out[t] and not off_out[t])
    only_off = sum(1 for t in shared if off_out[t] and not on_out[t])
    return AblationReport(
        on=_summarise(on_name, on_rows, {t: on_out[t] for t in shared}),
        off=_summarise(off_name, off_rows, {t: off_out[t] for t in shared}),
        only_on=only_on,
        only_off=only_off,
        mcnemar_p=mcnemar_exact(only_on, only_off),
    )


def render_markdown(report: AblationReport, *, model: str, flag: str) -> str:
    lines = [
        f"# Ablation: {flag} (model: {model})",
        "",
        "| arm | tasks | passed | pass@1 | 95% CI | tokens/solved median | p90 |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in (report.on, report.off):
        lines.append(
            f"| {arm.name} | {arm.total} | {arm.passed} | {arm.pass_rate:.2%} | "
            f"[{arm.ci_low:.2%}, {arm.ci_high:.2%}] | {arm.tokens_median:.0f} | "
            f"{arm.tokens_p90:.0f} |",
        )
    lines += [
        "",
        f"Paired discordant tasks: only {report.on.name} = {report.only_on}, "
        f"only {report.off.name} = {report.only_off}.",
        f"McNemar exact two-sided p = {report.mcnemar_p:.4g}.",
        "",
    ]
    return "\n".join(lines)
