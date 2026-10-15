"""Hard spend cap for live evals. Haiku only, by the owner's rule.

Before each model call the guard estimates the worst case (prompt estimate x 1.5,
plus the full output limit) and refuses the call if the ledger would pass the cap.
After the call it records the cost from the billed usage. The ledger is a file, so
the cap holds across separate runs that share an output directory.

Prices: Claude Haiku 5.5, USD per million tokens, prompts up to 100K tokens
(input 0.10, output 0.50; cache read ~0.1x input, 5-minute cache write ~1.25x).
Longer prompts are billed at a higher rate, so they are refused instead.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from codeagent.config import Price
from codeagent.providers.base import Message, ModelEvent, ModelRequest, Usage, UsageEvent
from codeagent.providers.protocol import Provider
from codeagent.providers.quota_errors import ProviderError

HAIKU = "claude-haiku-5-5"
HAIKU_PRICE = Price(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125)
MAX_PROMPT_TOKENS = 100_000
ESTIMATE_MARGIN = 1.5


def usage_cost(usage: Usage, price: Price = HAIKU_PRICE) -> float:
    return (
        usage.input * price.input
        + usage.output * price.output
        + usage.cache_read * price.cache_read
        + usage.cache_write * price.cache_write
    ) / 1_000_000


class SpendLedger:
    def __init__(self, path: Path, cap_usd: float) -> None:
        self.path = path
        self.cap_usd = cap_usd
        self.spent_usd = 0.0
        if path.exists():
            self.spent_usd = float(json.loads(path.read_text(encoding="utf-8"))["spent_usd"])

    @property
    def remaining_usd(self) -> float:
        return self.cap_usd - self.spent_usd

    def add(self, usd: float) -> None:
        self.spent_usd += usd
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"spent_usd": self.spent_usd, "cap_usd": self.cap_usd}
        self.path.write_text(json.dumps(payload), encoding="utf-8")


def _estimate_prompt_tokens(req: ModelRequest) -> int:
    chars = len(req.system) + sum(len(m.content or "") for m in req.messages)
    chars += sum(len(json.dumps(t.parameters)) + len(t.description) for t in req.tools)
    return chars // 4 + 1


class SpendGuardProvider:
    """Wraps a provider; refuses calls that could pass the cap; records billed cost."""

    def __init__(self, inner: Provider, ledger: SpendLedger) -> None:
        self._inner = inner
        self.ledger = ledger
        self.calls = 0

    def count_tokens(self, messages: list[Message]) -> int:
        return self._inner.count_tokens(messages)

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        if req.model != HAIKU:
            raise ProviderError(f"only Haiku ({HAIKU}) may be used for live runs, got {req.model}")
        prompt = _estimate_prompt_tokens(req)
        if prompt > MAX_PROMPT_TOKENS:
            raise ProviderError("prompt estimate exceeds 100K tokens; refused (higher price tier)")
        worst = (
            prompt * ESTIMATE_MARGIN * HAIKU_PRICE.input
            + req.max_output_tokens * HAIKU_PRICE.output
        ) / 1_000_000
        if worst > self.ledger.remaining_usd:
            raise ProviderError(
                f"spend cap: worst case ${worst:.4f} exceeds remaining "
                f"${self.ledger.remaining_usd:.4f} of ${self.ledger.cap_usd:.2f}",
            )
        self.calls += 1
        for event in self._inner.stream(req):
            if isinstance(event, UsageEvent):
                self.ledger.add(usage_cost(event.usage))
            yield event
