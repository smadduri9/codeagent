"""--non-interactive says what it does; --yes stays as a deprecated alias."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from codeagent.cli import app
from codeagent.providers.base import ModelEvent, Stop, StopReason, TextDelta, Usage, UsageEvent


def _script(tmp_path: Path) -> str:
    script: list[list[ModelEvent]] = [
        [
            TextDelta(text="done"),
            UsageEvent(usage=Usage(input=1, output=1)),
            Stop(reason=StopReason.STOP),
        ]
    ]
    path = tmp_path / "script.json"
    path.write_bytes(TypeAdapter(list[list[ModelEvent]]).dump_json(script))
    return str(path)


@pytest.mark.parametrize("command", ["run", "chat", "resume"])
def test_help_describes_non_interactive(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"], terminal_width=200)
    assert result.exit_code == 0
    # Rich adds colour codes around option names on CI; strip them before matching.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--non-interactive" in plain
    assert "Auto-approve" not in plain
    assert "--yes" not in plain


def test_non_interactive_flag_is_accepted(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["run", "goal", "--no-persist", "--non-interactive", "--fake-script", _script(tmp_path)],
    )
    assert result.exit_code == 0, result.stderr
    assert "deprecated" not in result.stderr


def test_yes_still_works_and_says_it_approves_nothing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["run", "goal", "--no-persist", "--yes", "--fake-script", _script(tmp_path)]
    )
    assert result.exit_code == 0, result.stderr
    assert "--yes is deprecated" in result.stderr
    assert "--non-interactive" in result.stderr
