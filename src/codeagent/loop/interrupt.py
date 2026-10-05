"""Cooperative interrupt handling (first Ctrl-C graceful, second immediate)."""

from __future__ import annotations

import signal
from dataclasses import dataclass


@dataclass
class InterruptController:
    """Testable interrupt state without requiring real signals."""

    graceful_pending: bool = False
    immediate: bool = False
    signal_count: int = 0
    _installed: bool = False

    def on_signal(self) -> None:
        self.signal_count += 1
        if self.signal_count >= 2:
            self.immediate = True
        self.graceful_pending = True

    def should_stop_before_tool(self) -> bool:
        return self.immediate

    def should_stop_after_current_tool(self) -> bool:
        return self.graceful_pending and not self.immediate

    def should_stop_after_model(self) -> bool:
        return self.graceful_pending

    def clear_graceful(self) -> None:
        self.graceful_pending = False


def install_sigint_handler(controller: InterruptController) -> None:
    if controller._installed:
        return

    def _handler(_signum: int, _frame: object) -> None:
        controller.on_signal()

    signal.signal(signal.SIGINT, _handler)
    controller._installed = True
