"""Rich rendering for streamed agent runs."""

from __future__ import annotations

from rich.console import Console

from codeagent.loop.observers import RunOutputObserver
from codeagent.providers.base import Message, MessageRole


class CliRunOutputRenderer(RunOutputObserver):
    """Stream model text and tool activity to the terminal."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console(stderr=True)
        self._text_open = False

    def _end_text(self) -> None:
        if self._text_open:
            self._console.print()
            self._text_open = False

    def on_text_delta(self, text: str) -> None:
        if not text:
            return
        self._text_open = True
        self._console.print(text, end="")

    def on_tool_announced(self, name: str) -> None:
        self._end_text()
        self._console.print(f"[dim]tool[/dim] [bold]{name}[/bold]")

    def on_tool_start(self, name: str) -> None:
        del name

    def on_tool_end(self, name: str, ok: bool) -> None:
        status = "[green]ok[/green]" if ok else "[red]failed[/red]"
        self._console.print(f"  [dim]{name}[/dim] {status}")

    def on_model_turn_end(self) -> None:
        self._end_text()

    def print_final_answer(self, history: list[Message]) -> None:
        """Print the last assistant message with non-empty content."""
        content = final_assistant_content(history)
        if content is None:
            return
        self._end_text()
        self._console.print()
        self._console.print("[bold]answer[/bold]")
        self._console.print(content)


def final_assistant_content(history: list[Message]) -> str | None:
    for message in reversed(history):
        if message.role is MessageRole.ASSISTANT and message.content:
            stripped = message.content.strip()
            if stripped:
                return message.content
    return None
