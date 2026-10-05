"""Evaluation runner CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

if TYPE_CHECKING:
    from evals.gate_analysis import GateAssessment
    from evals.live_agent import LiveTaskMetrics

console = Console(stderr=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS = REPO_ROOT / "evals" / "tasks"
DEFAULT_OUT = REPO_ROOT / "evals" / "baselines" / "live-core12"


def eval_command(
    live: Annotated[bool, typer.Option("--live", help="Run tasks with the live agent.")] = False,
    slice_name: Annotated[
        str | None,
        typer.Option("--slice", help="Task slice name under evals/slices/."),
    ] = None,
    resume: Annotated[bool, typer.Option("--resume", help="Resume from output state.")] = False,
    output: Annotated[Path, typer.Option("--output", help="Output directory.")] = DEFAULT_OUT,
    quota_stop: Annotated[
        int | None,
        typer.Option("--quota-stop", help="Stop after N live tasks."),
    ] = 3,
) -> None:
    """Run evaluation tasks in replay or live mode."""
    from evals.gate_analysis import assess_gate
    from evals.live_agent import LiveTaskMetrics
    from evals.runner import run_eval

    mode = "live" if live else "replay"
    quota = quota_stop if live else None
    state = run_eval(
        tasks_dir=TASKS,
        output_dir=output,
        mode=mode,
        resume=resume,
        quota_stop_after=quota,
        slice_name=slice_name or ("core12" if live else None),
    )
    aggregated_ok = sum(1 for row in state.results if row.ok)
    console.print(f"eval complete: {aggregated_ok}/{len(state.results)} runs recorded")
    if live:
        metrics = [
            LiveTaskMetrics(
                task_id=row.task_id,
                ok=row.ok,
                model_calls=row.model_calls,
                search_calls=row.search_calls,
                total_tool_calls=row.model_calls,
                tokens=row.tokens,
                error=row.error,
            )
            for row in state.results
            if row.mode == "live"
        ]
        assessment = assess_gate(metrics)
        _write_gate_conclusion(output, assessment, metrics)
        console.print(assessment.conclusion)
    raise typer.Exit(code=0)


def _write_gate_conclusion(
    output: Path,
    assessment: GateAssessment,
    metrics: list[LiveTaskMetrics],
) -> None:
    root = REPO_ROOT / "evals" / "baselines"
    path = root / "gate-conclusion.md"
    completed = assessment.tasks_run
    remaining = max(0, 12 - completed)
    lines = [
        "# Repository intelligence gate (DESIGN 9.1)",
        "",
        "## Live core12 baseline",
        "",
        f"Tasks completed: **{completed} / 12** in the `core12` slice.",
        f"Tasks passed: **{assessment.tasks_passed}**.",
        f"Search-call share on failed tasks: **{assessment.search_share_failed:.2f}** "
        "(threshold > 0.30 for gate path 1).",
        f"Tokens recorded (sum): **{sum(m.tokens for m in metrics)}**.",
        "",
        "## Conclusion",
        "",
        f"**{assessment.conclusion}**",
        "",
    ]
    if remaining:
        lines.append(
            "Resume with `codeagent eval --live --slice core12 --resume` when quota allows.",
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    partial = root / "live-core12-partial.md"
    try:
        out_rel = output.relative_to(REPO_ROOT)
    except ValueError:
        out_rel = output
    partial.write_text(
        "\n".join(
            [
                "# Live core12 baseline (partial)",
                "",
                f"| Tasks completed | {completed} / 12 |",
                f"| Tasks passed | {assessment.tasks_passed} |",
                f"| Search share (failed) | {assessment.search_share_failed:.2f} |",
                f"| Output dir | `{out_rel}` |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
