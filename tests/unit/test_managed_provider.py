"""Managed provider pacing and quota fallbacks."""

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
from codeagent.providers.managed import ManagedProvider
from codeagent.providers.quota_errors import QuotaExhaustedError


class _SequenceProvider:
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


def test_managed_provider_switches_model_on_quota_exhaustion() -> None:
    inner = _SequenceProvider(
        [QuotaExhaustedError("daily cap", reset_at=None), Stop(reason=StopReason.STOP)]
    )
    settings = Settings.model_validate({"model": {"main": "primary"}})
    managed = ManagedProvider(
        inner=inner,
        settings=settings,
        model="primary",
        fallback_models=["secondary"],
        sleeper=lambda _s: None,
    )
    req = ModelRequest(
        model="primary",
        system="sys",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        max_output_tokens=50,
        temperature=0.0,
    )
    events = list(managed.stream(req))
    assert len(events) == 1
    assert managed.events == [{"fallback_model": "secondary"}]
    assert inner.calls == 2


def test_managed_provider_raises_when_fallbacks_exhausted() -> None:
    inner = _SequenceProvider([QuotaExhaustedError("daily cap", reset_at=None)])
    settings = Settings()
    managed = ManagedProvider(
        inner=inner,
        settings=settings,
        model="primary",
        fallback_models=[],
        sleeper=lambda _s: None,
    )
    req = ModelRequest(
        model="primary",
        system="sys",
        messages=[Message(role=MessageRole.USER, content="hi")],
        tools=[],
        max_output_tokens=50,
        temperature=0.0,
    )
    with pytest.raises(QuotaExhaustedError):
        list(managed.stream(req))
