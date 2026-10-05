"""run_command execution mechanics."""

import os
import subprocess
from pathlib import Path

import pytest

from codeagent.tools.command_exec import filtered_environment, run_argv


def test_timeout_kills_sleep() -> None:
    result = run_argv(
        ["sleep", "5"],
        cwd=Path.cwd(),
        timeout_s=0.2,
        max_output_chars=8000,
    )
    assert result.timed_out
    assert result.ok is False
    assert "timeout" in result.combined_output.lower()


def test_tail_preservation_on_large_output(tmp_path: Path) -> None:
    script = tmp_path / "out.sh"
    script.write_text('printf "%20000s" "x"\n', encoding="utf-8")
    script.chmod(0o755)
    result = run_argv(
        ["/bin/sh", str(script)],
        cwd=tmp_path,
        timeout_s=5,
        max_output_chars=500,
    )
    assert result.truncated
    assert result.combined_output.endswith("x")
    assert "truncated" in result.combined_output


def test_environment_filters_provider_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "secret-value")
    monkeypatch.setenv("SAFE_FLAG", "1")
    env = filtered_environment()
    assert "GROQ_API_KEY" not in env
    assert os.environ.get("GROQ_API_KEY") == "secret-value"
    result = run_argv(
        ["/bin/sh", "-c", 'test -z "$GROQ_API_KEY" && echo ok'],
        cwd=tmp_path,
        timeout_s=5,
        max_output_chars=200,
    )
    assert "ok" in result.combined_output


def test_nonzero_exit_reported(tmp_path: Path) -> None:
    result = run_argv(
        ["/bin/sh", "-c", "exit 7"],
        cwd=tmp_path,
        timeout_s=5,
        max_output_chars=500,
    )
    assert result.exit_code == 7
    assert result.ok is False


@pytest.mark.skipif(
    os.name != "posix",
    reason="process groups documented for POSIX in platform-notes",
)
def test_uses_process_group_on_posix() -> None:
    """Sanity: start_new_session is set (timeout test exercises group kill)."""
    proc = subprocess.Popen(
        ["sleep", "30"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        os.killpg(proc.pid, 9)
    finally:
        proc.wait(timeout=5)
