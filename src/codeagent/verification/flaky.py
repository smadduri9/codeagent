from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlakyOutcome:
    flaky: bool


def evaluate_flaky(first_failed: bool, second_failed: bool | None) -> FlakyOutcome:
    if not first_failed or second_failed is None:
        return FlakyOutcome(flaky=False)
    return FlakyOutcome(flaky=first_failed and not second_failed)
