"""Validate eval task fixtures (size limits and broken/fixed checks)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MAX_FILES = 15
MAX_LINES = 150


@dataclass(frozen=True)
class TaskValidation:
    task_id: str
    ok: bool
    errors: tuple[str, ...]


def _count_fixture_files(task_dir: Path) -> list[Path]:
    skip = {"task.yaml", "broken.yaml", "verify.py", "__pycache__"}
    files: list[Path] = []
    for path in task_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in skip or path.suffix == ".pyc":
            continue
        if path.name == "task.yaml" and path.parent != task_dir:
            continue
        rel = path.relative_to(task_dir)
        if rel.parts[0] == ".git":
            continue
        files.append(path)
    return files


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def load_task(task_dir: Path) -> dict[str, Any]:
    return yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))


def run_check(task_dir: Path) -> int:
    task = load_task(task_dir)
    cmd = task["check"]["command"]
    return subprocess.run(cmd, cwd=task_dir, check=False).returncode


def apply_broken(task_dir: Path) -> None:
    broken_path = task_dir / "broken.yaml"
    if not broken_path.is_file():
        return
    spec = yaml.safe_load(broken_path.read_text(encoding="utf-8")) or {}
    for rel, content in (spec.get("files") or {}).items():
        path = task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if content is not None else "", encoding="utf-8")
    for rel in spec.get("delete") or []:
        path = task_dir / rel
        if path.is_file():
            path.unlink()


def validate_task(task_dir: Path) -> TaskValidation:
    errors: list[str] = []
    task = load_task(task_dir)
    task_id = str(task.get("id", task_dir.name))
    files = _count_fixture_files(task_dir)
    if len(files) > MAX_FILES:
        errors.append(f"too many fixture files: {len(files)} > {MAX_FILES}")
    for path in files:
        lines = _line_count(path)
        if lines > MAX_LINES:
            errors.append(f"{path.name} has {lines} lines > {MAX_LINES}")
    if not task.get("reference_transcript"):
        errors.append("missing reference_transcript")
    if run_check(task_dir) != 0:
        errors.append("check fails in fixed (committed) state")
    if (task_dir / "broken.yaml").is_file():
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "task"
            shutil.copytree(task_dir, copy_root)
            apply_broken(copy_root)
            if run_check(copy_root) == 0:
                errors.append("check should fail after broken overlay")
    return TaskValidation(task_id=task_id, ok=not errors, errors=tuple(errors))


def validate_all(tasks_root: Path) -> list[TaskValidation]:
    results: list[TaskValidation] = []
    for path in sorted(tasks_root.glob("*/task.yaml")):
        results.append(validate_task(path.parent))
    return results
