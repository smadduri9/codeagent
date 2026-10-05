"""Typed git subprocess wrapper (read-only helpers for tools and isolation)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitCommandError(RuntimeError):
    """Git returned a non-zero exit code."""

    def __init__(self, git_args: list[str], returncode: int, output: str) -> None:
        joined = " ".join(git_args)
        super().__init__(f"git {joined} failed ({returncode}): {output.strip()}")
        self.git_args = git_args
        self.returncode = returncode
        self.output = output


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int


def run_git(
    repo: Path,
    args: list[str],
    *,
    check: bool = True,
    input_text: str | None = None,
) -> GitResult:
    command = ["git", *args]
    completed = subprocess.run(
        command,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        input=input_text,
    )
    result = GitResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )
    if check and completed.returncode != 0:
        message = completed.stderr or completed.stdout
        raise GitCommandError(args, completed.returncode, message)
    return result
