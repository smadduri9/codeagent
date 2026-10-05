"""Security checks deferred until later phases."""

from pathlib import Path

import pytest

from codeagent.tools.command_exec import run_argv


def test_command_timeout_works() -> None:
    result = run_argv(
        ["sleep", "5"],
        cwd=Path.cwd(),
        timeout_s=0.2,
        max_output_chars=4000,
    )
    assert result.timed_out
    assert result.ok is False


@pytest.mark.skip(reason="overwrite protection requires edit_file hashing (P2-F4)")
def test_existing_user_modifications_not_silently_overwritten() -> None: ...
