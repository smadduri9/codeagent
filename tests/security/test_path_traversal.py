"""Security: workspace boundary enforcement."""

from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.permissions import Deny, PermissionRun, decide
from codeagent.providers.base import ToolCall
from codeagent.tools.paths import WorkspacePathError, resolve_workspace_path


def test_path_traversal_blocked(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(WorkspacePathError):
        resolve_workspace_path(root, "../../../etc/passwd")
    run = PermissionRun(workspace=root, settings=Settings())
    call = ToolCall(id="1", name="read_file", args={"path": "../../../etc/passwd"})
    assert isinstance(decide(call, call.args, run), Deny)


def test_symlink_escape_blocked(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    root.mkdir()
    link = root / "link"
    link.symlink_to(outside / "secret.txt")
    run = PermissionRun(workspace=root, settings=Settings())
    call = ToolCall(id="1", name="read_file", args={"path": "link"})
    assert isinstance(decide(call, call.args, run), Deny)
