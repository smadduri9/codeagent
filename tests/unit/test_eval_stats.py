"""Statistics helpers for eval reports."""

import pytest

from evals.stats import mcnemar_exact, median_p90, wilson_interval


def test_mcnemar_known_value() -> None:
    assert mcnemar_exact(8, 2) == pytest.approx(0.109375)


def test_mcnemar_no_discordant_pairs() -> None:
    assert mcnemar_exact(0, 0) == 1.0


def test_wilson_zero_successes_lower_bound_is_zero() -> None:
    low, _high = wilson_interval(0, 10)
    assert low == pytest.approx(0.0, abs=1e-9)


def test_wilson_half_successes() -> None:
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)


def test_median_and_p90() -> None:
    assert median_p90([1.0, 2.0, 3.0, 4.0, 5.0]) == (3.0, 5.0)


def test_median_p90_empty_raises() -> None:
    with pytest.raises(ValueError):
        median_p90([])
