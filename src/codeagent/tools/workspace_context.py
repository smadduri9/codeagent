"""Shared state for workspace file tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codeagent.config import ToolSettings
from codeagent.tools.read_tracker import ReadTracker


@dataclass
class FileChangedEvent:
    path: str
    diff: str


@dataclass
class WorkspaceToolContext:
    workspace: Path
    settings: ToolSettings
    read_tracker: ReadTracker = field(default_factory=ReadTracker)
    file_changed_events: list[FileChangedEvent] = field(default_factory=list)
