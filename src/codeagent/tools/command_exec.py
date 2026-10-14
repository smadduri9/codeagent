"""No-shell and shell command execution with timeouts and filtered environment."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from codeagent.tools.truncate import truncate_content

DEFAULT_TIMEOUT_S = 120
_BLOCKED_ENV_EXACT = frozenset(
    {
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
    },
)
_BLOCKED_ENV_SUFFIXES = ("_API_KEY", "_SECRET", "_TOKEN", "_PASSWORD")
_BASE_ALLOWED = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "TMPDIR",
        "TZ",
        "PYTHONPATH",
        "VIRTUAL_ENV",
    },
)


@dataclass(frozen=True)
class CommandRunResult:
    ok: bool
    combined_output: str
    exit_code: int | None
    duration_ms: int
    timed_out: bool
    truncated: bool


def _is_blocked_env_key(key: str) -> bool:
    upper = key.upper()
    if upper in _BLOCKED_ENV_EXACT:
        return True
    return any(upper.endswith(suffix) for suffix in _BLOCKED_ENV_SUFFIXES)


def _is_allowed_env_key(key: str, passthrough: Collection[str]) -> bool:
    if _is_blocked_env_key(key):
        return False
    return key in _BASE_ALLOWED or key.startswith("LC_") or key in passthrough


def filtered_environment(
    base: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
    *,
    passthrough: Collection[str] = (),
) -> dict[str, str]:
    """Build a child environment from an allowlist; secret-looking keys never pass."""
    source = dict(os.environ if base is None else base)
    result = {k: v for k, v in source.items() if _is_allowed_env_key(k, passthrough)}
    for key, value in (extra or {}).items():
        if not _is_blocked_env_key(key):
            result[key] = value
    return result


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.05)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    else:
        proc.kill()


def run_argv(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    env: Mapping[str, str] | None = None,
    max_output_chars: int,
) -> CommandRunResult:
    """Run a command without shell interpretation."""
    if not argv:
        return CommandRunResult(
            ok=False,
            combined_output="argv must not be empty",
            exit_code=None,
            duration_ms=0,
            timed_out=False,
            truncated=False,
        )
    child_env = filtered_environment(extra=env)
    start = time.perf_counter()
    timed_out = False
    try:
        if os.name == "posix":
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        else:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        try:
            stdout, _ = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(proc)
            stdout, _ = proc.communicate()
    except OSError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return CommandRunResult(
            ok=False,
            combined_output=str(exc),
            exit_code=None,
            duration_ms=duration_ms,
            timed_out=False,
            truncated=False,
        )
    duration_ms = int((time.perf_counter() - start) * 1000)
    combined = stdout or ""
    if timed_out:
        combined = f"{combined}\n[timeout after {timeout_s}s; process group killed]".lstrip("\n")
    capped, truncated = truncate_content(combined, max_output_chars, keep="tail")
    exit_code = proc.returncode
    ok = not timed_out and exit_code == 0
    return CommandRunResult(
        ok=ok,
        combined_output=capped,
        exit_code=exit_code,
        duration_ms=duration_ms,
        timed_out=timed_out,
        truncated=truncated,
    )
