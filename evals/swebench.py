"""SWE-bench Lite instance loader. Reads a local JSONL file only; never downloads."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SweInstance:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    test_patch: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]


def _as_list(value: Any) -> list[str]:
    """SWE-bench stores some test lists as JSON strings and some as real lists."""
    if isinstance(value, str):
        parsed = json.loads(value) if value.strip() else []
        return [str(item) for item in parsed]
    return [str(item) for item in value or []]


def load_instances(jsonl_path: Path, instance_ids: list[str]) -> list[SweInstance]:
    """Return the requested instances, in the order requested. Unknown ids raise KeyError."""
    wanted = list(instance_ids)
    found: dict[str, SweInstance] = {}
    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            iid = str(row["instance_id"])
            if iid not in wanted or iid in found:
                continue
            found[iid] = SweInstance(
                instance_id=iid,
                repo=str(row["repo"]),
                base_commit=str(row["base_commit"]),
                problem_statement=str(row.get("problem_statement", "")),
                test_patch=str(row.get("test_patch", "")),
                fail_to_pass=_as_list(row.get("FAIL_TO_PASS")),
                pass_to_pass=_as_list(row.get("PASS_TO_PASS")),
            )
    missing = [iid for iid in wanted if iid not in found]
    if missing:
        raise KeyError(f"instance ids not in {jsonl_path.name}: {', '.join(missing)}")
    return [found[iid] for iid in wanted]


def check_command(inst: SweInstance) -> list[str]:
    """The command that must pass for the instance to count as solved."""
    return ["python", "-m", "pytest", "-q", *inst.fail_to_pass]
