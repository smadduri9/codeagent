"""Track file reads for edit_file stale detection."""

from __future__ import annotations

import hashlib
from pathlib import Path


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReadTracker:
    """Stores content hashes for paths read during a run."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def record(self, path: Path, content: str) -> None:
        self._hashes[path.as_posix()] = content_hash(content)

    def was_read(self, path: Path) -> bool:
        return path.as_posix() in self._hashes

    def check_stale(self, path: Path, current_content: str) -> str | None:
        key = path.as_posix()
        if key not in self._hashes:
            return "file was not read in this run; read it before editing"
        if self._hashes[key] != content_hash(current_content):
            return "file changed on disk since last read; re-read before editing"
        return None
