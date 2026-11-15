"""Security: a directory grep never prints the contents of secret-looking files."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeagent.config import Settings, ToolSettings
from codeagent.permissions import Ask, PermissionRun, decide
from codeagent.providers.base import ToolCall
from codeagent.tools.file_tools import GrepArgs, handle_grep
from codeagent.tools.workspace_context import WorkspaceToolContext

pytestmark = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")

_XFAIL = pytest.mark.xfail(strict=True, reason="FIX-18")

_SECRET_FILES = ["server.pem", "id_rsa", "id_rsa.pub", "aws_credentials.json", "deep/my.pem"]


def _workspace(tmp_path: Path) -> WorkspaceToolContext:
    (tmp_path / "deep").mkdir()
    for name in _SECRET_FILES:
        (tmp_path / name).write_text("TOKEN=secret-value\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("TOKEN=public-example\n", encoding="utf-8")
    return WorkspaceToolContext(workspace=tmp_path, settings=ToolSettings())


@_XFAIL
@pytest.mark.parametrize(
    "args",
    [
        {"pattern": "TOKEN"},
        {"pattern": "TOKEN", "path": "."},
        {"pattern": "TOKEN", "path": "deep"},
        {"pattern": "TOKEN", "glob": "*.pem"},
        {"pattern": "TOKEN", "output_mode": "files"},
    ],
    ids=["no-path", "dot", "subdir", "glob-asks-for-pem", "files-mode"],
)
def test_directory_grep_skips_secret_files(tmp_path: Path, args: dict[str, str]) -> None:
    result = handle_grep(_workspace(tmp_path), GrepArgs(**args))  # type: ignore[arg-type]
    assert "secret-value" not in result.content
    for name in _SECRET_FILES:
        assert Path(name).name not in result.content


def test_directory_grep_still_finds_ordinary_files(tmp_path: Path) -> None:
    result = handle_grep(_workspace(tmp_path), GrepArgs(pattern="TOKEN"))
    assert result.ok
    assert "notes.txt" in result.content


def test_grep_on_a_named_secret_file_needs_approval(tmp_path: Path) -> None:
    _workspace(tmp_path)
    run = PermissionRun(workspace=tmp_path, settings=Settings())
    call = ToolCall(id="1", name="grep", args={"pattern": "TOKEN", "path": "server.pem"})
    assert isinstance(decide(call, call.args, run), Ask)
