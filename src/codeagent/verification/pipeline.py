from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from codeagent.config import VerifySettings
from codeagent.verification.checks import VerificationCheck
from codeagent.verification.flaky import evaluate_flaky


class CommandRunner:
    def run(self, command: list[str], *, cwd: Path, timeout_s: int) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, str(exc)
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))[-4000:]


class VerificationPipeline:
    def __init__(
        self,
        repo_root: Path,
        settings: VerifySettings,
        *,
        runner: CommandRunner | None = None,
        on_check: Callable[[VerificationCheck], None] | None = None,
        edited_py_files: list[Path] | None = None,
    ) -> None:
        self._root = repo_root
        self._settings = settings
        self._runner = runner or CommandRunner()
        self._on_check = on_check
        self._edited = edited_py_files or []

    def run(self, scope: str | None = None) -> list[VerificationCheck]:
        checks = [self._parse()]
        if scope in (None, "test", "tests"):
            checks.append(self._run_named("test", self._settings.test))
        if scope in (None, "lint"):
            checks.append(self._run_named("lint", self._settings.lint))
        return checks

    def _emit(self, check: VerificationCheck) -> VerificationCheck:
        if self._on_check:
            self._on_check(check)
        return check

    def _parse(self) -> VerificationCheck:
        if not self._edited:
            return self._emit(
                VerificationCheck(
                    name="parse",
                    status="skipped",
                    command=None,
                    duration_ms=0,
                    evidence="no edits",
                ),
            )
        for path in self._edited:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        return self._emit(
            VerificationCheck(
                name="parse",
                status="pass",
                command=None,
                duration_ms=0,
                evidence="ok",
            ),
        )

    def _run_named(self, name: str, command: list[str] | None) -> VerificationCheck:
        if command is None:
            return self._emit(
                VerificationCheck(
                    name=name,
                    status="unavailable",
                    command=None,
                    duration_ms=0,
                    evidence="unconfigured",
                ),
            )
        start = time.perf_counter()
        code, evidence = self._runner.run(
            command, cwd=self._root, timeout_s=self._settings.timeout_s
        )
        ms = int((time.perf_counter() - start) * 1000)
        if code == 0:
            return self._emit(
                VerificationCheck(
                    name=name,
                    status="pass",
                    command=command,
                    duration_ms=ms,
                    evidence=evidence,
                ),
            )
        if name == "test":
            code2, _ = self._runner.run(command, cwd=self._root, timeout_s=self._settings.timeout_s)
            if evaluate_flaky(True, code2 != 0).flaky:
                return self._emit(
                    VerificationCheck(
                        name=name,
                        status="flaky",
                        command=command,
                        duration_ms=ms,
                        evidence=evidence,
                    ),
                )
        return self._emit(
            VerificationCheck(
                name=name,
                status="fail",
                command=command,
                duration_ms=ms,
                evidence=evidence,
            ),
        )
