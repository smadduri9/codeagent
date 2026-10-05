"""Run budget limits derived from settings."""

from __future__ import annotations

from dataclasses import dataclass

from codeagent.config import Price, Settings


@dataclass(frozen=True, slots=True)
class RunLimits:
    max_iterations: int
    max_tool_calls: int
    max_total_tokens: int
    max_cost_usd: float
    max_runtime_minutes: int
    prices: dict[str, Price]
    model: str

    @classmethod
    def from_settings(cls, settings: Settings, model: str) -> RunLimits:
        limits = settings.limits
        return cls(
            max_iterations=limits.max_iterations,
            max_tool_calls=limits.max_tool_calls,
            max_total_tokens=limits.max_total_tokens,
            max_cost_usd=limits.max_cost_usd,
            max_runtime_minutes=limits.max_runtime_minutes,
            prices=dict(settings.prices),
            model=model,
        )

    def cost_guard_enabled(self) -> bool:
        if not self.prices:
            return False
        return any(
            price.input > 0 or price.output > 0 or price.cache_read > 0
            for price in self.prices.values()
        )
