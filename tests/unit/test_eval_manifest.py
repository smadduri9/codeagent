"""Eval repeats and run manifest."""

import json
from pathlib import Path

from evals.runner import run_eval

TASKS_DIR_FOR_TESTS = Path(__file__).resolve().parents[2] / "evals" / "tasks"


def test_repeats_produce_one_row_per_task_and_repeat(tmp_path: Path) -> None:
    state = run_eval(
        tasks_dir=TASKS_DIR_FOR_TESTS,
        output_dir=tmp_path,
        mode="replay",
        slice_name="core12",
        repeats=2,
    )
    tasks = {r.task_id for r in state.results}
    assert len(state.results) == 2 * len(tasks)
    assert {r.repeat for r in state.results} == {0, 1}


def test_manifest_records_run_identity(tmp_path: Path) -> None:
    run_eval(
        tasks_dir=TASKS_DIR_FOR_TESTS,
        output_dir=tmp_path,
        mode="replay",
        slice_name="core12",
        repeats=2,
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "replay"
    assert manifest["repeats"] == 2
    assert len(manifest["tasks"]) == 12
    for key in ("git_commit", "config_sha256", "prompt_hash", "started_at", "model", "provider"):
        assert key in manifest
