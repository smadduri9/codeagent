from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EvalResult:
    task_id: str
    ok: bool
    mode: str
    tokens: int = 0
    policy_violations: int = 0
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class EvalState:
    completed: set[str] = field(default_factory=set)
    results: list[EvalResult] = field(default_factory=list)


def load_task(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_eval(
    *,
    tasks_dir: Path,
    output_dir: Path,
    mode: str,
    resume: bool = False,
    quota_stop_after: int | None = None,
) -> EvalState:
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"
    state = EvalState()
    if resume and state_path.is_file():
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        state.completed = set(raw.get("completed", []))
        state.results = [EvalResult(**row) for row in raw.get("results", [])]
    paths = sorted(tasks_dir.glob("*/task.yaml"))
    live = 0
    for path in paths:
        task = load_task(path)
        task_id = str(task.get("id", path.parent.name))
        if task_id in state.completed:
            continue
        if mode == "live" and quota_stop_after is not None and live >= quota_stop_after:
            break
        if mode == "replay":
            ok = bool(task.get("reference_transcript"))
        else:
            cmd = task["check"]["command"]
            ok = subprocess.run(cmd, cwd=path.parent, check=False).returncode == 0
            live += 1
        state.results.append(EvalResult(task_id=task_id, ok=ok, mode=mode))
        state.completed.add(task_id)
        state_path.write_text(
            json.dumps(
                {
                    "completed": sorted(state.completed),
                    "results": [r.__dict__ for r in state.results],
                }
            ),
            encoding="utf-8",
        )
    (output_dir / "results.json").write_text(
        json.dumps([r.__dict__ for r in state.results], indent=2), encoding="utf-8"
    )
    with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(EvalResult.__dataclass_fields__))
        writer.writeheader()
        for row in state.results:
            writer.writerow(row.__dict__)
    ok = sum(1 for r in state.results if r.ok)
    total = len(state.results) or 1
    (output_dir / "report.md").write_text(f"success rate: {ok}/{total}\n", encoding="utf-8")
    return state
