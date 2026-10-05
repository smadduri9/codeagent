from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evals.task_validate import run_check


@dataclass
class EvalResult:
    task_id: str
    ok: bool
    mode: str
    tokens: int = 0
    policy_violations: int = 0
    duration_s: float = 0.0
    error: str | None = None
    runs: int = 1


@dataclass
class EvalState:
    completed: set[str] = field(default_factory=set)
    results: list[EvalResult] = field(default_factory=list)


def load_task(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_task_dirs(tasks_dir: Path, *, slice_name: str | None = None) -> list[Path]:
    if slice_name is None:
        return sorted({p.parent for p in tasks_dir.glob("*/task.yaml")}, key=lambda p: p.name)
    slice_path = tasks_dir.parent / "slices" / f"{slice_name}.txt"
    ids = {
        line.strip()
        for line in slice_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    return sorted(
        [tasks_dir / task_id for task_id in ids if (tasks_dir / task_id / "task.yaml").is_file()],
        key=lambda p: p.name,
    )


def _aggregate(results: list[EvalResult]) -> list[EvalResult]:
    grouped: dict[str, list[EvalResult]] = {}
    for row in results:
        grouped.setdefault(row.task_id, []).append(row)
    out: list[EvalResult] = []
    for task_id, rows in sorted(grouped.items()):
        ok = sum(1 for r in rows if r.ok)
        total = len(rows)
        out.append(
            EvalResult(
                task_id=task_id,
                ok=ok == total,
                mode=rows[0].mode,
                tokens=sum(r.tokens for r in rows),
                policy_violations=sum(r.policy_violations for r in rows),
                duration_s=sum(r.duration_s for r in rows),
                error=None if ok == total else f"{ok}/{total} runs passed",
                runs=total,
            )
        )
    return out


def run_eval(
    *,
    tasks_dir: Path,
    output_dir: Path,
    mode: str,
    resume: bool = False,
    quota_stop_after: int | None = None,
    slice_name: str | None = None,
    repeats: int = 1,
) -> EvalState:
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"
    state = EvalState()
    if resume and state_path.is_file():
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        state.completed = set(raw.get("completed", []))
        state.results = [EvalResult(**row) for row in raw.get("results", [])]
    task_dirs = list_task_dirs(tasks_dir, slice_name=slice_name)
    live_runs = 0
    for task_dir in task_dirs:
        task = load_task(task_dir / "task.yaml")
        task_id = str(task.get("id", task_dir.name))
        if task_id in state.completed:
            continue
        if mode == "live" and quota_stop_after is not None and live_runs >= quota_stop_after:
            break
        for _ in range(max(1, repeats)):
            start = time.monotonic()
            error: str | None = None
            if mode == "replay":
                ok = bool(task.get("reference_transcript")) and run_check(task_dir) == 0
                if not task.get("reference_transcript"):
                    error = "missing reference_transcript"
            else:
                ok = run_check(task_dir) == 0
                live_runs += 1
            state.results.append(
                EvalResult(
                    task_id=task_id,
                    ok=ok,
                    mode=mode,
                    duration_s=time.monotonic() - start,
                    error=error,
                )
            )
        state.completed.add(task_id)
        state_path.write_text(
            json.dumps(
                {
                    "completed": sorted(state.completed),
                    "results": [r.__dict__ for r in state.results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    aggregated = _aggregate(state.results)
    (output_dir / "results.json").write_text(
        json.dumps([r.__dict__ for r in aggregated], indent=2), encoding="utf-8"
    )
    with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(EvalResult.__dataclass_fields__))
        writer.writeheader()
        for row in aggregated:
            writer.writerow(row.__dict__)
    ok = sum(1 for r in aggregated if r.ok)
    total = len(aggregated) or 1
    behind = sum(r.runs for r in aggregated) - total
    (output_dir / "report.md").write_text(
        "\n".join(
            [
                f"mode: {mode}",
                f"success rate: {ok}/{total}",
                f"aggregate runs behind rate: {behind}",
                f"tasks completed: {len(state.completed)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return state
