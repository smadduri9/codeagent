"""Fault-injecting provider wrapper for reliability tests and evals.

Never used by the CLI. Each fault is applied to one provider call, identified by
its 0-based index. Other calls pass through to the wrapped provider unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from codeagent.providers.base import (
    ModelEvent,
    ModelRequest,
    ToolCallArgsDelta,
    ToolCallEnd,
)
from codeagent.providers.protocol import Provider
from codeagent.providers.quota_errors import ProviderError, RateLimitError

FaultKind = Literal["rate_limit", "server_error", "timeout", "truncate", "bad_tool_json"]


@dataclass(frozen=True)
class Fault:
    kind: FaultKind
    on_call: int


class FaultyProvider:
    def __init__(self, inner: Provider, faults: list[Fault]) -> None:
        self._inner = inner
        self._faults = {fault.on_call: fault for fault in faults}
        self._calls = 0

    def count_tokens(self, messages: list[object]) -> int:
        return self._inner.count_tokens(messages)  # type: ignore[arg-type]

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        index = self._calls
        self._calls += 1
        fault = self._faults.get(index)
        if fault is None:
            yield from self._inner.stream(req)
            return
        if fault.kind == "rate_limit":
            raise RateLimitError("429 rate limit (injected)", retry_after_s=0.0)
        if fault.kind == "server_error":
            raise ProviderError("500 internal server error (injected)")
        if fault.kind == "timeout":
            raise ProviderError("request timeout (injected)")
        yield from self._partial(req, fault.kind)

    def _partial(self, req: ModelRequest, kind: FaultKind) -> Iterator[ModelEvent]:
        corrupted = False
        for event in self._inner.stream(req):
            if kind == "truncate" and isinstance(event, ToolCallArgsDelta):
                yield event
                return
            if kind == "bad_tool_json" and not corrupted and isinstance(event, ToolCallEnd):
                yield ToolCallArgsDelta(id=event.call.id, delta='{"path": ')
                corrupted = True
                return
            yield event
