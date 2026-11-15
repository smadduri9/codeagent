"""edit_file keeps a file's line endings and rejects an empty search string."""

from __future__ import annotations

from pathlib import Path

from codeagent.config import ToolSettings
from codeagent.providers.base import ToolCall
from codeagent.tools.base import ToolResult
from codeagent.tools.registry import ToolRegistry


def _edit(tmp_path: Path, raw: bytes, args: dict[str, object]) -> tuple[ToolResult, bytes]:
    target = tmp_path / "file.txt"
    target.write_bytes(raw)
    registry = ToolRegistry()
    registry.register_filesystem_tools(tmp_path, ToolSettings())
    registry.run(ToolCall(id="r", name="read_file", args={"path": "file.txt"}))
    result = registry.run(ToolCall(id="e", name="edit_file", args={"path": "file.txt", **args}))
    return result, target.read_bytes()


def test_crlf_file_stays_crlf(tmp_path: Path) -> None:
    result, after = _edit(tmp_path, b"a\r\nb\r\nc\r\n", {"old_string": "b", "new_string": "z"})
    assert result.ok
    assert after == b"a\r\nz\r\nc\r\n"


def test_crlf_file_stays_crlf_for_a_multi_line_replacement(tmp_path: Path) -> None:
    result, after = _edit(
        tmp_path, b"a\r\nb\r\nc\r\n", {"old_string": "a\nb", "new_string": "x\ny\nz"}
    )
    assert result.ok
    assert after == b"x\r\ny\r\nz\r\nc\r\n"


def test_lf_file_stays_lf(tmp_path: Path) -> None:
    result, after = _edit(tmp_path, b"a\nb\nc\n", {"old_string": "b", "new_string": "z"})
    assert result.ok
    assert after == b"a\nz\nc\n"


def test_mixed_line_endings_are_normalised_to_lf_as_before(tmp_path: Path) -> None:
    result, after = _edit(tmp_path, b"a\r\nb\nc\n", {"old_string": "b", "new_string": "z"})
    assert result.ok
    assert after == b"a\nz\nc\n"


def test_empty_old_string_with_replace_all_is_rejected(tmp_path: Path) -> None:
    result, after = _edit(
        tmp_path, b"abc\n", {"old_string": "", "new_string": "-", "replace_all": True}
    )
    assert not result.ok
    assert "old_string" in result.content
    assert after == b"abc\n"


def test_empty_old_string_without_replace_all_is_rejected(tmp_path: Path) -> None:
    result, after = _edit(tmp_path, b"abc\n", {"old_string": "", "new_string": "-"})
    assert not result.ok
    assert after == b"abc\n"
