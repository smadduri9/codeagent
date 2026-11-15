"""Rate-limit handling waits for the time the provider asked for (DESIGN 8.20)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from codeagent.config import Settings
from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelEvent,
    ModelRequest,
    Stop,
    StopReason,
)
from codeagent.providers.managed import ManagedProvider, _parse_retry_after
from codeagent.providers.quota_errors import QuotaExhaustedError

_GROQ_429 = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model `m` on tokens "
    "per minute (TPM): Limit 8000, Used 7900, Requested 600. Please try again in 7.66s.'}}"
)


class _Sequence:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def count_tokens(self, messages: list[Message]) -> int:
        return 10

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        yield Stop(reason=StopReason.STOP)


def _request() -> ModelRequest:
    return ModelRequest(
        model="m",
        system="sys",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        max_output_tokens=50,
        temperature=0.0,
    )


def test_retry_after_is_read_from_the_wait_hint_not_the_status_code() -> None:
    cases = {
        _GROQ_429.lower(): 7.66,
        "error code: 429 - please try again in 430ms.": 0.43,
        "error code: 429 - please try again in 1m26.4s.": 86.4,
        "error code: 429 - please try again in 2m.": 120.0,
        "429 too many requests; retry-after: 12": 12.0,
        "error code: 429": 1.0,
        "rate limit reached": 1.0,
    }
    for message, expected in cases.items():
        assert _parse_retry_after(message) == pytest.approx(expected), message


def test_short_rate_limit_waits_then_retries() -> None:
    inner = _Sequence([RuntimeError(_GROQ_429), Stop(reason=StopReason.STOP)])
    slept: list[float] = []
    managed = ManagedProvider(inner=inner, settings=Settings(), model="m", sleeper=slept.append)
    events = list(managed.stream(_request()))
    assert len(events) == 1
    assert inner.calls == 2
    assert len(slept) == 1
    assert 7.66 <= slept[0] <= 7.66 + 0.25


def test_wait_longer_than_max_wait_is_quota_exhaustion() -> None:
    inner = _Sequence([RuntimeError("Error code: 429 - Please try again in 10m0s.")])
    slept: list[float] = []
    managed = ManagedProvider(inner=inner, settings=Settings(), model="m", sleeper=slept.append)
    with pytest.raises(QuotaExhaustedError):
        list(managed.stream(_request()))
    assert slept == []


def test_repeated_rate_limits_give_up() -> None:
    inner = _Sequence([RuntimeError(_GROQ_429) for _ in range(6)])
    managed = ManagedProvider(inner=inner, settings=Settings(), model="m", sleeper=lambda _s: None)
    with pytest.raises(QuotaExhaustedError):
        list(managed.stream(_request()))
    assert inner.calls <= 4


def test_pacing_waits_for_the_bucket_to_refill() -> None:
    now = [1000.0]
    slept: list[float] = []

    def sleeper(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    settings = Settings.model_validate(
        {"rate_limits": {"m": {"rpm": 1, "rpd": 100, "tpm": 100000, "tpd": 1000000}}}
    )
    inner = _Sequence([Stop(reason=StopReason.STOP), Stop(reason=StopReason.STOP)])
    managed = ManagedProvider(
        inner=inner, settings=settings, model="m", clock=lambda: now[0], sleeper=sleeper
    )
    list(managed.stream(_request()))
    assert slept == []
    list(managed.stream(_request()))
    assert slept == [pytest.approx(60.0)]
    assert inner.calls == 2
