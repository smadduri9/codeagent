"""Subset selection is deterministic and respects tiers, filters and caps."""

import json

from evals.select_swe30 import patch_size, select, tier


def _row(i: int, repo: str, lines: int, n_tests: int = 1) -> dict[str, object]:
    patch = "--- a/x\n+++ b/x\n" + "\n".join(f"+line{k}" for k in range(lines))
    return {
        "instance_id": f"{repo.split('/')[1]}-{i}",
        "repo": repo,
        "patch": patch,
        "FAIL_TO_PASS": json.dumps([f"t::{k}" for k in range(n_tests)]),
    }


def test_patch_size_ignores_file_headers() -> None:
    assert patch_size("--- a/x\n+++ b/x\n+new\n-old\n context\n") == 2


def test_tiers() -> None:
    assert (tier(4), tier(5), tier(10), tier(11)) == ("easy", "medium", "medium", "hard")


def test_selection_is_deterministic_and_filtered() -> None:
    rows = (
        [_row(i, "sympy/sympy", 2) for i in range(20)]
        + [_row(i, "pytest-dev/pytest", 8) for i in range(20)]
        + [_row(i, "pallets/flask", 30) for i in range(20)]
        + [_row(i, "django/django", 2) for i in range(20)]  # excluded repo
        + [_row(100 + i, "sympy/sympy", 2, n_tests=5) for i in range(5)]  # too many tests
    )
    caps = {"sympy/sympy": 3, "pytest-dev/pytest": 3, "pallets/flask": 3}
    first = select(rows, caps=caps, per_tier=3)
    assert first == select(rows, caps=caps, per_tier=3)
    assert all(len(ids) == 3 for ids in first.values())
    flat = [i for ids in first.values() for i in ids]
    assert not any(i.startswith("django") for i in flat)
    assert not any(i.startswith("sympy-10") for i in flat)
