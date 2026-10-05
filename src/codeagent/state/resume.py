"""Working-tree reconciliation and stale read detection on resume."""

from __future__ import annotations

from pathlib import Path

from codeagent.state.store import StateStore
from codeagent.tools.read_tracker import content_hash


def reconcile_files_read(
    store: StateStore,
    run_id: str,
    repo_root: Path,
) -> list[str]:
    """Return human-readable warnings for externally changed files."""
    warnings: list[str] = []
    recorded = store.list_files_read(run_id)
    for rel_path, recorded_hash in recorded.items():
        path = repo_root / rel_path
        if not path.is_file():
            warnings.append(f"file missing since last run: {rel_path}")
            continue
        current = content_hash(path.read_text(encoding="utf-8"))
        if current != recorded_hash:
            warnings.append(f"file changed externally: {rel_path}")
    return warnings


def stale_read_paths(
    store: StateStore,
    run_id: str,
    repo_root: Path,
) -> list[str]:
    """Paths whose on-disk content no longer matches the recorded read hash."""
    stale: list[str] = []
    for rel_path, recorded_hash in store.list_files_read(run_id).items():
        path = repo_root / rel_path
        if not path.is_file():
            stale.append(rel_path)
            continue
        if content_hash(path.read_text(encoding="utf-8")) != recorded_hash:
            stale.append(rel_path)
    return stale
