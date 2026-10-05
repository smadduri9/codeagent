from pathlib import Path

from evals.runner import list_task_dirs, run_eval
from evals.task_validate import validate_all

TASKS = Path(__file__).resolve().parents[2] / "evals" / "tasks"


def test_fixture_validation() -> None:
    results = validate_all(TASKS)
    failures = [r for r in results if not r.ok]
    assert not failures, failures


def test_core12_slice_lists_twelve_tasks() -> None:
    core = list_task_dirs(TASKS, slice_name="core12")
    assert len(core) == 12


def test_replay_runner_all_tasks(tmp_path: Path) -> None:
    out = tmp_path / "out"
    state = run_eval(tasks_dir=TASKS, output_dir=out, mode="replay")
    assert len(state.results) == len(list_task_dirs(TASKS))
    assert (out / "results.json").is_file()
    assert (out / "summary.csv").is_file()
    assert (out / "report.md").is_file()
    assert all(r.ok for r in state.results)
