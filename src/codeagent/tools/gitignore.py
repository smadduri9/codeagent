"""Minimal gitignore matching for directory listings."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def load_gitignore_patterns(root: Path) -> list[str]:
    """Load non-comment patterns from the repository ``.gitignore``."""
    path = root / ".gitignore"
    if not path.is_file():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def _match_one(rel_posix: str, name: str, pattern: str) -> bool:
    if pattern.startswith("/"):
        pattern = pattern[1:]
        return fnmatch.fnmatchcase(rel_posix, pattern) or fnmatch.fnmatchcase(
            rel_posix, pattern.rstrip("/")
        )
    if "/" in pattern:
        return fnmatch.fnmatchcase(rel_posix, pattern) or fnmatch.fnmatchcase(
            rel_posix, pattern.rstrip("/")
        )
    return fnmatch.fnmatchcase(name, pattern)


def is_ignored(relative_path: Path, patterns: list[str]) -> bool:
    """Return whether ``relative_path`` (under the repo root) is ignored."""
    if not patterns:
        return False
    rel_posix = relative_path.as_posix().lstrip("./")
    name = relative_path.name
    ignored = False
    for pattern in patterns:
        if pattern.startswith("!"):
            if _match_one(rel_posix, name, pattern[1:]):
                ignored = False
            continue
        if pattern.endswith("/"):
            if _match_one(rel_posix, name, pattern[:-1]) or name == pattern[:-1]:
                ignored = True
            continue
        if _match_one(rel_posix, name, pattern):
            ignored = True
    return ignored
