"""SWE-bench instance loader: parses JSONL and builds the check command."""

import json
from pathlib import Path

from evals.swebench import check_command, load_instances

_ROWS = [
    {
        "instance_id": "demo__repo-1",
        "repo": "demo/repo",
        "base_commit": "abc123",
        "problem_statement": "Fix the thing.",
        "test_patch": "diff --git a/t.py b/t.py",
        "FAIL_TO_PASS": json.dumps(["tests/test_a.py::test_one"]),
        "PASS_TO_PASS": json.dumps(["tests/test_a.py::test_zero"]),
    },
    {
        "instance_id": "demo__repo-2",
        "repo": "demo/repo",
        "base_commit": "def456",
        "problem_statement": "Other thing.",
        "test_patch": "",
        "FAIL_TO_PASS": ["tests/test_b.py::test_two"],
        "PASS_TO_PASS": [],
    },
]


def _write(path: Path) -> None:
    path.write_text("\n".join(json.dumps(row) for row in _ROWS) + "\n", encoding="utf-8")


def test_loads_selected_instances_and_parses_json_lists(tmp_path: Path) -> None:
    jsonl = tmp_path / "swe.jsonl"
    _write(jsonl)
    instances = load_instances(jsonl, ["demo__repo-2", "demo__repo-1"])
    # Returned in the order requested, not the order in the file.
    assert [i.instance_id for i in instances] == ["demo__repo-2", "demo__repo-1"]
    assert instances[0].fail_to_pass == ["tests/test_b.py::test_two"]
    assert instances[1].fail_to_pass == ["tests/test_a.py::test_one"]
    assert instances[1].base_commit == "abc123"


def test_check_command_runs_fail_to_pass_tests(tmp_path: Path) -> None:
    jsonl = tmp_path / "swe.jsonl"
    _write(jsonl)
    inst = load_instances(jsonl, ["demo__repo-1"])[0]
    assert check_command(inst) == ["python", "-m", "pytest", "-q", "tests/test_a.py::test_one"]


def test_unknown_ids_are_reported_not_silently_dropped(tmp_path: Path) -> None:
    jsonl = tmp_path / "swe.jsonl"
    _write(jsonl)
    try:
        load_instances(jsonl, ["missing__id-9"])
    except KeyError as exc:
        assert "missing__id-9" in str(exc)
    else:
        raise AssertionError("expected KeyError for an unknown instance id")
