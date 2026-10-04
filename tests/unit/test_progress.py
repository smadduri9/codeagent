"""Keep the durable tracker aligned with the authoritative feature plan."""

import re
from collections import Counter
from pathlib import Path


def test_every_planned_feature_appears_once() -> None:
    root = Path(__file__).resolve().parents[2]
    planned = re.findall(r"^\*\*(P\d+-F\d+) ", (root / "BUILD_PLAN.md").read_text(), re.M)
    tracked = re.findall(r"^\| (P\d+-F\d+) \|", (root / "docs/PROGRESS.md").read_text(), re.M)
    assert planned
    assert len(planned) == len(set(planned))
    assert Counter(tracked) == Counter(planned)
