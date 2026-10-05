"""Optional cost from the configured price table."""

from __future__ import annotations

from codeagent.config import Price, Settings
from codeagent.providers.base import Usage


def prices_active(settings: Settings) -> bool:
    if not settings.prices:
        return False
    return any(
        price.input > 0 or price.output > 0 or price.cache_read > 0
        for price in settings.prices.values()
    )


def compute_cost(model: str, usage: Usage, settings: Settings) -> tuple[float | None, str | None]:
    """Return USD cost or (None, note) when prices are inactive or missing."""
    if not prices_active(settings):
        return None, "cost skipped: all configured prices are zero"
    price = settings.prices.get(model)
    if price is None:
        return None, f"cost skipped: no price table entry for model {model!r}"
    usd = (
        usage.input * price.input
        + usage.output * price.output
        + usage.cache_read * price.cache_read
    ) / 1_000_000
    return usd, None


def lookup_price(settings: Settings, model: str) -> Price | None:
    return settings.prices.get(model)
