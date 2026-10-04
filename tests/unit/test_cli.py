"""Exercise the installed CLI's public entrypoint without a provider."""

import subprocess
import sys

from typer.testing import CliRunner

from codeagent.cli import app


def test_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "deterministic permissions" in result.output


def test_module_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "codeagent.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Usage" in result.stdout
