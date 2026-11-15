"""Verification only counts when at least one check actually ran and passed."""

from __future__ import annotations

import sys
from pathlib import Path

from codeagent.config import Settings, VerifySettings
from codeagent.state.store import StateStore
from codeagent.tools.base import ToolResult
from codeagent.tools.verification_tools import (
    RunTestsArgs,
    RunVerificationArgs,
    handle_run_tests,
    handle_run_verification,
)

_PASS = [sys.executable, "-c", "raise SystemExit(0)"]
_FAIL = [sys.executable, "-c", "raise SystemExit(1)"]


def _verify(tmp_path: Path, verify: VerifySettings, scope: str | None = None) -> ToolResult:
    settings = Settings(verify=verify)
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    try:
        return handle_run_verification(
            RunVerificationArgs(scope=scope),
            repo_root=tmp_path,
            settings=settings,
            store=store,
            run_id=run_id,
            edited_py_files=[],
        )
    finally:
        store.close()


def test_nothing_configured_is_not_a_pass(tmp_path: Path) -> None:
    result = _verify(tmp_path, VerifySettings())
    assert not result.ok
    assert "test:unavailable" in result.content
    assert "no check ran" in result.content


def test_run_tests_without_a_test_command_is_not_a_pass(tmp_path: Path) -> None:
    settings = Settings()
    store = StateStore(tmp_path / "state.db")
    run_id = store.create_run(repo_path=tmp_path, goal="g", model="m")
    try:
        result = handle_run_tests(
            RunTestsArgs(),
            repo_root=tmp_path,
            settings=settings,
            store=store,
            run_id=run_id,
            edited_py_files=[],
        )
    finally:
        store.close()
    assert not result.ok


def test_a_passing_check_is_a_pass(tmp_path: Path) -> None:
    result = _verify(tmp_path, VerifySettings(test=_PASS))
    assert result.ok
    assert "test:pass" in result.content
    assert "no check ran" not in result.content


def test_a_failing_check_is_a_failure(tmp_path: Path) -> None:
    result = _verify(tmp_path, VerifySettings(test=_FAIL, lint=_PASS))
    assert not result.ok
    assert "test:fail" in result.content


def test_one_passing_check_is_enough_when_others_are_unavailable(tmp_path: Path) -> None:
    result = _verify(tmp_path, VerifySettings(lint=_PASS))
    assert result.ok
    assert "lint:pass" in result.content
