"""Workspace path resolution tests."""

import os
from pathlib import Path

import pytest

from codeagent.tools.paths import WorkspacePathError, resolve_workspace_path


def test_resolve_relative_inside(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    child = root / "a" / "b.txt"
    child.parent.mkdir(parents=True)
    child.write_text("ok", encoding="utf-8")
    resolved = resolve_workspace_path(root, "a/b.txt")
    assert resolved == child.resolve()


def test_resolve_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "ws2"
    root.mkdir()
    with pytest.raises(WorkspacePathError, match="escapes"):
        resolve_workspace_path(root, "../outside")


def test_resolve_absolute_inside(tmp_path: Path) -> None:
    root = tmp_path / "ws3"
    root.mkdir()
    file_path = root / "x.txt"
    file_path.write_text("x", encoding="utf-8")
    resolved = resolve_workspace_path(root, str(file_path.resolve()))
    assert resolved == file_path.resolve()


def test_resolve_absolute_outside(tmp_path: Path) -> None:
    root = tmp_path / "ws4"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(WorkspacePathError, match="escapes"):
        resolve_workspace_path(root, str(outside.resolve()))


def test_resolve_nonexistent_child(tmp_path: Path) -> None:
    root = tmp_path / "ws5"
    root.mkdir()
    resolved = resolve_workspace_path(root, "new/nested.txt")
    assert resolved == (root / "new" / "nested.txt").resolve()


def test_resolve_symlink_within(tmp_path: Path) -> None:
    root = tmp_path / "ws6"
    root.mkdir()
    target = root / "real.txt"
    target.write_text("t", encoding="utf-8")
    link = root / "link.txt"
    os.symlink(target, link)
    resolved = resolve_workspace_path(root, "link.txt")
    assert resolved == target.resolve()


def test_resolve_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "ws7"
    root.mkdir()
    outside = tmp_path / "out7"
    outside.mkdir()
    outside_file = outside / "secret.txt"
    outside_file.write_text("s", encoding="utf-8")
    link = root / "escape"
    os.symlink(outside_file, link)
    with pytest.raises(WorkspacePathError, match="escapes"):
        resolve_workspace_path(root, "escape")
