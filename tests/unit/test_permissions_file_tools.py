"""Table-driven file tool permission decisions."""

from pathlib import Path

import pytest

from codeagent.config import Settings
from codeagent.permissions import Allow, Ask, Deny, PermissionRun, decide
from codeagent.providers.base import ToolCall


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".codeagent").mkdir()
    return root


def _run(workspace: Path, *, edit_mode: str = "allow") -> PermissionRun:
    settings = Settings.model_validate({"permissions": {"edit_mode": edit_mode}})
    return PermissionRun(workspace=workspace, settings=settings)


@pytest.mark.parametrize(
    ("tool", "args", "expected"),
    [
        ("read_file", {"path": "src/main.py"}, Allow),
        ("list_dir", {"path": "src"}, Allow),
        ("glob", {"pattern": "**/*.py"}, Allow),
        ("grep", {"path": "src", "pattern": "hi"}, Allow),
        ("read_file", {"path": ".env"}, Ask),
        ("read_file", {"path": "../outside"}, Deny),
        ("write_file", {"path": "src/new.py", "content": "x"}, Allow),
        ("write_file", {"path": ".env", "content": "x"}, Deny),
        ("write_file", {"path": ".git/config", "content": "x"}, Deny),
        ("edit_file", {"path": "src/main.py", "old_string": "a", "new_string": "b"}, Allow),
        ("delete_path", {"path": "src/main.py"}, Ask),
        ("move_path", {"src": "src/main.py", "dst": "src/moved.py"}, Ask),
    ],
)
def test_file_tool_decisions(
    workspace: Path,
    tool: str,
    args: dict[str, object],
    expected: type,
) -> None:
    run = _run(workspace)
    call = ToolCall(id="1", name=tool, args=args)
    decision = decide(call, args, run)
    assert isinstance(decision, expected)


def test_edit_mode_ask_flips_writes(workspace: Path) -> None:
    run = _run(workspace, edit_mode="ask")
    call = ToolCall(id="1", name="write_file", args={"path": "src/x.py", "content": "a"})
    decision = decide(call, call.args, run)
    assert isinstance(decision, Ask)
