"""Optional Docker-backed command execution (DESIGN 8.15)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from codeagent.tools.command_exec import CommandRunResult, run_argv

DEFAULT_DOCKER_IMAGE = "python:3.12-bookworm-slim"
WarnFn = Callable[[str], None]


@dataclass(frozen=True)
class DockerSettings:
    image: str = DEFAULT_DOCKER_IMAGE
    network: str = "none"


def docker_cli_available(*, timeout_s: float = 5.0) -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        completed = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _warn_fallback(message: str, warn: WarnFn | None) -> None:
    text = f"WARNING: {message} Falling back to host command execution."
    if warn is not None:
        warn(text)
    else:
        import sys

        print(text, file=sys.stderr)


def run_argv_docker(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None,
    max_output_chars: int,
    settings: DockerSettings | None = None,
    warn: WarnFn | None = None,
) -> CommandRunResult:
    """Run ``argv`` inside a container with the workspace bind-mounted."""
    cfg = settings or DockerSettings()
    workspace = cwd.resolve()
    if not docker_cli_available():
        _warn_fallback("Docker is not available.", warn)
        return run_argv(
            argv,
            cwd=workspace,
            timeout_s=timeout_s,
            env=env,
            max_output_chars=max_output_chars,
        )
    mount = f"{workspace}:{workspace}"
    container_argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        cfg.network,
        "-v",
        mount,
        "-w",
        str(workspace),
        cfg.image,
        *argv,
    ]
    result = run_argv(
        container_argv,
        cwd=workspace,
        timeout_s=timeout_s,
        env=env,
        max_output_chars=max_output_chars,
    )
    if not result.ok and result.exit_code is None and "docker" in result.combined_output.lower():
        _warn_fallback("Docker command failed to start.", warn)
        return run_argv(
            argv,
            cwd=workspace,
            timeout_s=timeout_s,
            env=env,
            max_output_chars=max_output_chars,
        )
    return result


def execute_argv(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None,
    max_output_chars: int,
    isolation_mode: str,
    warn: WarnFn | None = None,
) -> CommandRunResult:
    """Route execution to Docker or the host based on ``isolation_mode``."""
    if isolation_mode == "docker":
        return run_argv_docker(
            argv,
            cwd=cwd,
            timeout_s=timeout_s,
            env=env,
            max_output_chars=max_output_chars,
            warn=warn,
        )
    return run_argv(
        argv,
        cwd=cwd,
        timeout_s=timeout_s,
        env=env,
        max_output_chars=max_output_chars,
    )
