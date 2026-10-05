"""Optional hooks for streaming agent output to a UI layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RunOutputObserver(Protocol):
    """Callbacks from the agent loop; implementations must not raise."""

    def on_text_delta(self, text: str) -> None:
        """Model text chunk for the current turn."""

    def on_tool_announced(self, name: str) -> None:
        """Model chose a tool (streaming event, before execution)."""

    def on_tool_start(self, name: str) -> None:
        """Tool execution is starting."""

    def on_tool_end(self, name: str, ok: bool) -> None:
        """Tool execution finished."""

    def on_model_turn_end(self) -> None:
        """Model turn finished (text and/or tool calls collected)."""


class NullRunOutputObserver:
    """No-op observer for tests and headless runs."""

    def on_text_delta(self, text: str) -> None:
        del text

    def on_tool_announced(self, name: str) -> None:
        del name

    def on_tool_start(self, name: str) -> None:
        del name

    def on_tool_end(self, name: str, ok: bool) -> None:
        del name, ok

    def on_model_turn_end(self) -> None:
        return
