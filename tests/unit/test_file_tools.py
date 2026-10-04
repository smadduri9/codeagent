"""Filesystem tool handler tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeagent.config import ToolSettings
from codeagent.providers.base import ToolCall
from codeagent.tools.file_tools import READ_FILE_MAX_BYTES
from codeagent.tools.registry import ToolRegistry

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "search_repo"


def _registry(workspace: Path) -> tuple[ToolRegistry, object]:
    registry = ToolRegistry()
    ctx = registry.register_filesystem_tools(workspace, ToolSettings(read_default_lines=5))
    return registry, ctx


def _run(registry: ToolRegistry, name: str, args: dict[str, object]) -> object:
    return registry.run(ToolCall(id="1", name=name, args=args))


def test_read_file_line_numbers_and_limit(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "f.txt").write_text("one\n two\nthree\n", encoding="utf-8")
    registry, _ = _registry(workspace)
    result = _run(registry, "read_file", {"path": "f.txt", "offset": 2, "limit": 1})
    assert result.ok is True
    assert "2| two" in result.content


def test_read_file_rejects_binary(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "bin.dat").write_bytes(b"text\x00more")
    registry, _ = _registry(workspace)
    result = _run(registry, "read_file", {"path": "bin.dat"})
    assert result.ok is False
    assert "binary" in result.content


def test_read_file_rejects_huge_file(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    huge = workspace / "big.txt"
    huge.write_bytes(b"x" * (READ_FILE_MAX_BYTES + 1))
    registry, _ = _registry(workspace)
    result = _run(registry, "read_file", {"path": "big.txt"})
    assert result.ok is False
    assert "size cap" in result.content


def test_read_file_truncation_marker(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    lines = "\n".join(f"line {i}" for i in range(200))
    (workspace / "long.txt").write_text(lines + "\n", encoding="utf-8")
    settings = ToolSettings(max_output_chars=80, read_default_lines=200)
    registry = ToolRegistry()
    registry.register_filesystem_tools(workspace, settings)
    result = _run(registry, "read_file", {"path": "long.txt"})
    assert result.ok is True
    assert result.truncated is True
    assert "narrow the search" in result.content


def test_list_dir_respects_gitignore(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    shutil.copytree(FIXTURE_ROOT, workspace)
    registry, _ = _registry(workspace)
    result = _run(registry, "list_dir", {"path": "."})
    assert result.ok is True
    assert "src/" in result.content
    assert "ignored.log" not in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
def test_glob_finds_py_files() -> None:
    registry, _ = _registry(FIXTURE_ROOT)
    result = _run(registry, "glob", {"pattern": "**/*.py"})
    assert result.ok is True
    assert "src/main.py" in result.content


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")
def test_grep_modes() -> None:
    registry, _ = _registry(FIXTURE_ROOT)
    files = _run(registry, "grep", {"pattern": "ALPHA", "output_mode": "files"})
    assert files.ok is True
    assert "src/main.py" in files.content
    count = _run(registry, "grep", {"pattern": "ALPHA", "output_mode": "count"})
    assert count.ok is True
    assert "main.py" in count.content
    lines = _run(registry, "grep", {"pattern": "ALPHA", "output_mode": "lines", "context": 0})
    assert lines.ok is True
    assert "ALPHA" in lines.content


def test_grep_missing_rg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry, _ = _registry(workspace)
    monkeypatch.setattr("codeagent.tools.file_tools._rg_path", lambda: None)
    result = _run(registry, "grep", {"pattern": "x", "output_mode": "files"})
    assert result.ok is False
    assert "ripgrep" in result.content


def test_write_file_refuses_existing(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "a.txt"
    target.write_text("old", encoding="utf-8")
    registry, ctx = _registry(workspace)
    result = _run(registry, "write_file", {"path": "a.txt", "content": "new"})
    assert result.ok is False
    assert "already exists" in result.content
    create = _run(registry, "write_file", {"path": "nested/new.txt", "content": "hi"})
    assert create.ok is True
    assert (workspace / "nested" / "new.txt").read_text(encoding="utf-8") == "hi"
    assert len(ctx.file_changed_events) == 1


def test_edit_file_requires_read(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "m.py").write_text("x = 1\n", encoding="utf-8")
    registry, _ = _registry(workspace)
    result = _run(
        registry,
        "edit_file",
        {"path": "m.py", "old_string": "x = 1", "new_string": "x = 2"},
    )
    assert result.ok is False
    assert "read" in result.content


def test_edit_file_ambiguous_and_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "dup.py").write_text("a\na\n", encoding="utf-8")
    registry, _ = _registry(workspace)
    _run(registry, "read_file", {"path": "dup.py"})
    missing = _run(
        registry,
        "edit_file",
        {"path": "dup.py", "old_string": "z", "new_string": "y"},
    )
    assert missing.ok is False
    assert "0 matches" in missing.content
    ambiguous = _run(
        registry,
        "edit_file",
        {"path": "dup.py", "old_string": "a", "new_string": "b"},
    )
    assert ambiguous.ok is False
    assert "lines 1, 2" in ambiguous.content


def test_edit_file_stale_after_external_change(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = workspace / "stale.py"
    path.write_text("v = 1\n", encoding="utf-8")
    registry, _ = _registry(workspace)
    _run(registry, "read_file", {"path": "stale.py"})
    path.write_text("v = 9\n", encoding="utf-8")
    result = _run(
        registry,
        "edit_file",
        {"path": "stale.py", "old_string": "v = 1", "new_string": "v = 2"},
    )
    assert result.ok is False
    assert "re-read" in result.content


def test_edit_file_parse_error_reported(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "bad.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    registry, _ = _registry(workspace)
    _run(registry, "read_file", {"path": "bad.py"})
    result = _run(
        registry,
        "edit_file",
        {"path": "bad.py", "old_string": "def f():", "new_string": "def f("},
    )
    assert result.ok is True
    assert "syntax error" in result.content.lower()


def test_move_and_delete(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = workspace / "a.txt"
    src.write_text("a", encoding="utf-8")
    (workspace / "dir").mkdir()
    registry, _ = _registry(workspace)
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    blocked = _run(registry, "move_path", {"src": "a.txt", "dst": str(outside)})
    assert blocked.ok is False
    moved = _run(registry, "move_path", {"src": "a.txt", "dst": "dir/b.txt"})
    assert moved.ok is True
    assert not src.exists()
    assert (workspace / "dir" / "b.txt").is_file()
    deleted = _run(registry, "delete_path", {"path": "dir", "recursive": True})
    assert deleted.ok is True
    assert not (workspace / "dir").exists()


def test_delete_path_risk_metadata() -> None:
    registry = ToolRegistry()
    registry.register_filesystem_tools(FIXTURE_ROOT)
    delete_spec = registry.lookup("delete_path")
    read_spec = registry.lookup("read_file")
    assert delete_spec.risk_level == "DESTRUCTIVE"
    assert read_spec.risk_level == "READ_ONLY"


def test_glob_missing_rg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry, _ = _registry(workspace)
    monkeypatch.setattr("codeagent.tools.file_tools._rg_path", lambda: None)
    result = _run(registry, "glob", {"pattern": "*.py"})
    assert result.ok is False
    assert "ripgrep" in result.content
