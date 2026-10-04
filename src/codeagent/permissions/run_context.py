"""Permission evaluation context (no model-visible text)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codeagent.config import PermissionSettings, Settings


@dataclass
class PermissionRun:
    """Inputs for ``decide``; must not include chat history or tool output."""

    workspace: Path
    settings: Settings
    interactive: bool = True
    session_allowed_hashes: set[str] = field(default_factory=set)

    @property
    def permissions(self) -> PermissionSettings:
        return self.settings.permissions
