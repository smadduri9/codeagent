"""Security: deletion approval and secret paths."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.permissions import Ask, Deny, PermissionRun, decide
from codeagent.providers.base import ToolCall


def test_deletion_requires_approval(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "x.txt").write_text("a", encoding="utf-8")
    run = PermissionRun(workspace=root, settings=Settings())
    call = ToolCall(id="1", name="delete_path", args={"path": "x.txt"})
    assert isinstance(decide(call, call.args, run), Ask)


def test_secret_path_read_requires_approval(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text("K=1\n", encoding="utf-8")
    run = PermissionRun(workspace=root, settings=Settings())
    call = ToolCall(id="1", name="read_file", args={"path": ".env"})
    decision = decide(call, call.args, run)
    assert isinstance(decision, Ask)


def test_secret_path_write_denied(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    run = PermissionRun(workspace=root, settings=Settings())
    call = ToolCall(id="1", name="write_file", args={"path": ".env", "content": "x"})
    assert isinstance(decide(call, call.args, run), Deny)
