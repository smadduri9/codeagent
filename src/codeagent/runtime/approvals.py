"""Interactive approval prompts for the CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass

import typer
from rich.console import Console

from codeagent.permissions.approvals import ApprovalChoice
from codeagent.permissions.types import Allow, Ask, Decision, Deny, RiskLevel
from codeagent.providers.base import ToolCall

_MAX_VALUE_CHARS = 400


def describe_arguments(call: ToolCall) -> list[str]:
    """One line per argument, JSON-encoded so control characters never reach the terminal."""
    lines: list[str] = []
    for key, value in call.args.items():
        text = json.dumps(value, ensure_ascii=True, default=str)
        if len(text) > _MAX_VALUE_CHARS:
            text = f"{text[:_MAX_VALUE_CHARS]}... [{len(text)} chars total]"
        lines.append(f"  {key}: {text}")
    return lines


@dataclass
class CliApprovalPrompt:
    """Prompt the operator for Ask-tier tool calls."""

    console: Console
    choice: ApprovalChoice = "deny"

    def resolve(self, call: ToolCall, ask: Ask) -> Decision:
        self.console.print(
            f"[yellow]approval[/yellow] tool={call.name} risk={ask.risk_level} — {ask.reason}",
        )
        for line in describe_arguments(call):
            # Arguments are model-supplied: print them literally, never as markup.
            self.console.print(line, markup=False, highlight=False, soft_wrap=True)
        answer = (
            typer.prompt(
                "Allow? [y] once / [s] session / [n] deny",
                default="n",
            )
            .strip()
            .lower()
        )
        if answer in {"y", "yes", "once"}:
            self.choice = "once"
            level = ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT
            return Allow(risk_level=level, decided_by="user")
        if answer in {"s", "session"}:
            self.choice = "session"
            level = ask.risk_level or RiskLevel.EXTERNAL_SIDE_EFFECT
            return Allow(risk_level=level, decided_by="user")
        self.choice = "deny"
        return Deny(ask.reason, risk_level=ask.risk_level)
