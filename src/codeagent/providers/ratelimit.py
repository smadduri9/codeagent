"""Client-side token bucket pacing with injectable clock."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic

Clock = Callable[[], float]


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    clock: Clock = field(default=monotonic)
    tokens: float = field(init=False)
    last: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last = self.clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self.last)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last = now

    def try_consume(self, amount: float) -> bool:
        self._refill()
        if amount > self.tokens:
            return False
        self.tokens -= amount
        return True

    def consume_or_wait(self, amount: float) -> float:
        """Return seconds to wait before ``amount`` tokens are available (0 if ready)."""
        self._refill()
        if amount <= self.tokens:
            self.tokens -= amount
            return 0.0
        missing = amount - self.tokens
        return missing / self.refill_per_second if self.refill_per_second > 0 else 0.0


@dataclass(frozen=True)
class ModelRateLimits:
    rpm: int
    tpm: int


def buckets_for_model(
    limits: ModelRateLimits,
    *,
    clock: Clock = monotonic,
) -> tuple[TokenBucket, TokenBucket]:
    request_bucket = TokenBucket(
        capacity=float(limits.rpm),
        refill_per_second=limits.rpm / 60.0,
        clock=clock,
    )
    token_bucket = TokenBucket(
        capacity=float(limits.tpm),
        refill_per_second=limits.tpm / 60.0,
        clock=clock,
    )
    return request_bucket, token_bucket
