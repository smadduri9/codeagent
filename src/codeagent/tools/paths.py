"""Resolve paths against the workspace root."""

from pathlib import Path


class WorkspacePathError(ValueError):
    """The path leaves the workspace or is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def resolve_workspace_path(workspace: Path, raw: str) -> Path:
    """Return ``realpath`` of ``raw`` when it lies inside ``workspace``.

    Rejects traversal outside the workspace and symlinks that resolve outside it.
    Nonexistent paths are allowed when their existing parent chain stays inside.
    """
    if not raw or not raw.strip():
        raise WorkspacePathError("path must not be empty")
    root = workspace.resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    if resolved != root and not resolved.is_relative_to(root):
        raise WorkspacePathError("path escapes workspace")
    return resolved
