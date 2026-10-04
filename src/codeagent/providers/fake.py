"""Scripted provider for offline tests and replay harnesses."""

from collections.abc import Iterator, Sequence
from json import dumps

from codeagent.providers.base import (
    Message,
    ModelEvent,
    ModelRequest,
    Stop,
    StopReason,
    Usage,
    UsageEvent,
)


class FakeProvider:
    """Replay a fixed list of turns; each ``stream`` call consumes the next turn."""

    def __init__(self, turns: Sequence[Sequence[ModelEvent]]) -> None:
        self._turns = [list(events) for events in turns]
        self._next = 0

    @property
    def turns_remaining(self) -> int:
        return len(self._turns) - self._next

    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]:
        del req  # scripted replay ignores the live request
        if self._next >= len(self._turns):
            yield UsageEvent(usage=Usage(input=0, output=0))
            yield Stop(reason=StopReason.ERROR)
            return
        events = self._turns[self._next]
        self._next += 1
        yield from events

    def count_tokens(self, messages: list[Message]) -> int:
        total_chars = 0
        for message in messages:
            if message.content:
                total_chars += len(message.content)
            for call in message.tool_calls:
                total_chars += len(call.id) + len(call.name) + len(dumps(call.args, sort_keys=True))
        return max(1, total_chars // 4)
