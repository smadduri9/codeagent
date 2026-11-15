"""Rate limiting, retries, and quota persistence around a provider."""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from time import sleep
from typing import Protocol

from codeagent.config import RateLimits, Settings
from codeagent.providers.base import Message, ModelEvent, ModelRequest
from codeagent.providers.quota_errors import (
    ContextOverflowError,
    QuotaExhaustedError,
    RateLimitError,
)
from codeagent.providers.ratelimit import ModelRateLimits, TokenBucket, buckets_for_model
from codeagent.state.store import QuotaSnapshot, StateStore


class InnerProvider(Protocol):
    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]: ...

    def count_tokens(self, messages: list[Message]) -> int: ...


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass
class RateLimitHeaders:
    requests_remaining: int | None = None
    tokens_remaining: int | None = None
    reset_at: str | None = None
    retry_after_s: float | None = None


@dataclass
class ManagedProvider:
    """Paces requests and handles retry-after / quota exhaustion."""

    inner: InnerProvider
    settings: Settings
    store: StateStore | None = None
    model: str = "model"
    clock: Clock = field(default_factory=lambda: __import__("time").monotonic)
    sleeper: Sleeper = sleep
    request_bucket: TokenBucket | None = None
    token_bucket: TokenBucket | None = None
    fallback_models: list[str] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        limits = self.settings.rate_limits.get(self.model)
        if limits is not None:
            req_limits = ModelRateLimits(rpm=limits.rpm, tpm=limits.tpm)
            self.request_bucket, self.token_bucket = buckets_for_model(
                req_limits,
                clock=self.clock,
            )

    def count_tokens(self, messages: list[Message]) -> int:
        return self.inner.count_tokens(messages)

    def _estimate_charge(self, req: ModelRequest) -> float:
        tokens = self.inner.count_tokens(req.messages) + req.max_output_tokens
        return max(1.0, float(tokens))

    def _pace(self, charge: float) -> None:
        if self.request_bucket is not None:
            self._wait_for(self.request_bucket, 1.0)
        if self.token_bucket is not None:
            self._wait_for(self.token_bucket, charge)

    def _wait_for(self, bucket: TokenBucket, amount: float) -> None:
        """Sleep until the bucket has refilled, then charge it (DESIGN 8.20)."""
        wait = bucket.consume_or_wait(amount)
        if wait > 0:
            self.sleeper(min(wait, float(self.settings.quota.max_wait_s)))
            bucket.consume_or_wait(amount)

    def _persist_headers(self, headers: RateLimitHeaders) -> None:
        if self.store is None:
            return
        self.store.upsert_quota(
            QuotaSnapshot(
                model=self.model,
                requests_remaining=headers.requests_remaining,
                tokens_remaining=headers.tokens_remaining,
                reset_at=headers.reset_at,
            ),
        )

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        charge = self._estimate_charge(req)
        self._pace(charge)
        attempts = 0
        active_model = self.model
        while True:
            attempts += 1
            active_req = (
                req if active_model == req.model else req.model_copy(update={"model": active_model})
            )
            try:
                yield from self._stream_with_hooks(active_req)
                return
            except RateLimitError as exc:
                if exc.retry_after_s <= self.settings.quota.max_wait_s and attempts < 4:
                    self.sleeper(exc.retry_after_s + random.random() * 0.25)
                    continue
                raise QuotaExhaustedError(
                    "retry-after exceeds max wait",
                    reset_at=None,
                ) from exc
            except QuotaExhaustedError:
                if self.fallback_models:
                    active_model = self.fallback_models.pop(0)
                    self.events.append({"fallback_model": active_model})
                    continue
                raise
            except ContextOverflowError:
                raise
            except Exception as exc:  # noqa: BLE001 - mapped below
                message = str(exc).lower()
                if "429" in message or "rate limit" in message:
                    retry = _parse_retry_after(message)
                    if retry <= self.settings.quota.max_wait_s and attempts < 4:
                        self.sleeper(retry + random.random() * 0.25)
                        continue
                    raise QuotaExhaustedError("rate limit exhausted", reset_at=None) from exc
                if "too large" in message:
                    raise ContextOverflowError(str(exc)) from exc
                raise

    def _stream_with_hooks(self, req: ModelRequest) -> Iterator[ModelEvent]:
        if hasattr(self.inner, "stream_with_headers"):
            stream = self.inner.stream_with_headers
            events, headers = stream(req)
            self._persist_headers(headers)
            yield from events
            return
        yield from self.inner.stream(req)


_TRY_AGAIN = re.compile(r"try again in\s+(?:(\d+)m(?!s))?\s*(?:(\d+(?:\.\d+)?)(ms|s))?")
_RETRY_AFTER = re.compile(r"retry[-_ ]after[\s:=\"']+(\d+(?:\.\d+)?)")


def _parse_retry_after(message: str) -> float:
    """Seconds the provider asked us to wait; 1.0 when the (lowercased) text has no hint.

    Never reads a bare number: the HTTP status code is not a wait time.
    """
    hint = _TRY_AGAIN.search(message)
    if hint is not None and (hint.group(1) or hint.group(2)):
        seconds = float(hint.group(1) or 0) * 60.0
        if hint.group(2):
            value = float(hint.group(2))
            seconds += value / 1000.0 if hint.group(3) == "ms" else value
        return seconds
    header = _RETRY_AFTER.search(message)
    if header is not None:
        return float(header.group(1))
    return 1.0


def limits_from_settings(settings: Settings, model: str) -> RateLimits | None:
    return settings.rate_limits.get(model)
