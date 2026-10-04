"""Provider protocol for model streaming."""

from collections.abc import Iterator
from typing import Protocol

from codeagent.providers.base import Message, ModelEvent, ModelRequest


class Provider(Protocol):
    """Stream normalized model events and estimate prompt tokens."""

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        """Yield streaming events for one model turn."""
        ...

    def count_tokens(self, messages: list[Message]) -> int:
        """Estimate input tokens for a message list (approximate is acceptable)."""
        ...
