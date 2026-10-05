"""Docker command runner and git isolation mapping."""

from pathlib import Path
from unittest.mock import patch

import pytest

from codeagent.config import IsolationSettings, ToolSettings
from codeagent.isolation.docker import docker_cli_available, execute_argv, run_argv_docker
from codeagent.isolation.session import begin_isolation, git_isolation_mode
from codeagent.tools.command_exec import CommandRunResult
from codeagent.tools.command_tools import (
    CommandToolContext,
    RunCommandArgs,
    handle_run_command,
)


def test_git_isolation_mode_maps_docker_to_worktree() -> None:
    assert git_isolation_mode(IsolationSettings(mode="docker")) == "worktree"
    assert git_isolation_mode(IsolationSettings(mode="branch")) == "branch"


def test_docker_mode_still_creates_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git_init(repo)
    session = begin_isolation(repo, "dock-1", IsolationSettings(mode="docker"))
    try:
        assert session.mode == "worktree"
        assert session.workspace != repo or (repo / ".codeagent" / "worktrees").exists()
    finally:
        session.cleanup()


def test_execute_argv_falls_back_when_docker_missing(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    warnings: list[str] = []

    def capture(msg: str) -> None:
        warnings.append(msg)

    with patch("codeagent.isolation.docker.docker_cli_available", return_value=False):
        result = execute_argv(
            ["python", "-c", "print('ok')"],
            cwd=ws,
            timeout_s=5,
            env=None,
            max_output_chars=1000,
            isolation_mode="docker",
            warn=capture,
        )
    assert result.ok
    assert "ok" in result.combined_output
    assert warnings


def test_run_argv_docker_invokes_docker_run(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    calls: list[list[str]] = []

    def fake_run_argv(argv, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(argv)
        from codeagent.tools.command_exec import CommandRunResult

        return CommandRunResult(
            ok=True,
            combined_output="",
            exit_code=0,
            duration_ms=1,
            timed_out=False,
            truncated=False,
        )

    with patch("codeagent.isolation.docker.docker_cli_available", return_value=True):
        with patch("codeagent.isolation.docker.run_argv", side_effect=fake_run_argv):
            run_argv_docker(["echo", "hi"], cwd=ws, timeout_s=1, env=None, max_output_chars=100)
    assert calls
    assert calls[0][0] == "docker"
    assert "--network" in calls[0]
    assert "none" in calls[0]


def test_handle_run_command_respects_docker_mode(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = CommandToolContext(
        workspace=ws,
        settings=ToolSettings(),
        isolation_mode="docker",
    )
    with patch("codeagent.tools.command_tools.execute_argv") as mocked:
        mocked.return_value = CommandRunResult(
            ok=True,
            combined_output="",
            exit_code=0,
            duration_ms=0,
            timed_out=False,
            truncated=False,
        )
        handle_run_command(ctx, RunCommandArgs(argv=["true"]))
    assert mocked.call_args.kwargs["isolation_mode"] == "docker"


@pytest.mark.live
@pytest.mark.skipif(not docker_cli_available(), reason="docker daemon not available")
def test_live_docker_echo() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        result = run_argv_docker(
            ["echo", "sandbox"],
            cwd=ws,
            timeout_s=30,
            env=None,
            max_output_chars=200,
        )
        assert result.ok
        assert "sandbox" in result.combined_output


def run_git_init(repo: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "f"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)
