"""Spend guard: Haiku only, worst-case check before each call, persisted ledger."""

import json
from pathlib import Path

import pytest

from codeagent.providers.base import (
    Message,
    MessageRole,
    ModelRequest,
    Stop,
    StopReason,
    TextDelta,
    Usage,
    UsageEvent,
)
from codeagent.providers.fake import FakeProvider
from codeagent.providers.quota_errors import ProviderError
from evals.spend import HAIKU, HAIKU_PRICE, SpendGuardProvider, SpendLedger


def _req(model: str = HAIKU, chars: int = 400, max_out: int = 1000) -> ModelRequest:
    return ModelRequest(
        system="s",
        messages=[Message(role=MessageRole.USER, content="x" * chars)],
        tools=[],
        model=model,
        max_output_tokens=max_out,
    )


def _turn(inp: int, out: int, cache_read: int = 0, cache_write: int = 0) -> list[object]:
    return [
        TextDelta(text="ok"),
        UsageEvent(
            usage=Usage(input=inp, output=out, cache_read=cache_read, cache_write=cache_write)
        ),
        Stop(reason=StopReason.STOP),
    ]


def test_records_actual_cost_from_usage(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.json", cap_usd=3.0)
    guard = SpendGuardProvider(FakeProvider([_turn(1_000_000, 0)]), ledger)
    list(guard.stream(_req()))
    assert ledger.spent_usd == pytest.approx(HAIKU_PRICE.input)
    assert json.loads((tmp_path / "spend.json").read_text())["spent_usd"] == pytest.approx(0.10)


def test_cache_tokens_are_priced(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.json", cap_usd=3.0)
    guard = SpendGuardProvider(FakeProvider([_turn(0, 0, 1_000_000, 1_000_000)]), ledger)
    list(guard.stream(_req()))
    assert ledger.spent_usd == pytest.approx(HAIKU_PRICE.cache_read + HAIKU_PRICE.cache_write)


def test_refuses_call_whose_worst_case_would_pass_the_cap(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.json", cap_usd=0.0005)
    inner = FakeProvider([_turn(1, 1)])
    guard = SpendGuardProvider(inner, ledger)
    with pytest.raises(ProviderError, match="spend cap"):
        list(guard.stream(_req(max_out=2000)))  # 2000 output tokens alone is $0.001
    assert inner.turns_remaining == 1  # the provider was never called


def test_refuses_non_haiku_models(tmp_path: Path) -> None:
    guard = SpendGuardProvider(FakeProvider([_turn(1, 1)]), SpendLedger(tmp_path / "s.json", 3.0))
    with pytest.raises(ProviderError, match="Haiku"):
        list(guard.stream(_req(model="claude-sonnet-5-5")))


def test_refuses_prompts_over_100k_tokens(tmp_path: Path) -> None:
    guard = SpendGuardProvider(FakeProvider([_turn(1, 1)]), SpendLedger(tmp_path / "s.json", 3.0))
    with pytest.raises(ProviderError, match="100K"):
        list(guard.stream(_req(chars=500_000)))


def test_ledger_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "spend.json"
    first = SpendLedger(path, cap_usd=3.0)
    first.add(1.25)
    assert SpendLedger(path, cap_usd=3.0).spent_usd == pytest.approx(1.25)
