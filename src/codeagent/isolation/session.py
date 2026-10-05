"""Worktree isolation with branch-mode fallback."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from codeagent.config import IsolationSettings
from codeagent.isolation.checkpoint import CheckpointStore
from codeagent.isolation.git_wrapper import run_git
from codeagent.isolation.lock import RunLock


class IsolationError(RuntimeError):
    """Isolation could not be started or cleaned up."""


class DirtyTreeChoice(StrEnum):
    ABORT = "abort"
    PROCEED = "proceed"


@dataclass
class IsolationSession:
    git_root: Path
    run_id: str
    mode: str
    workspace: Path
    user_root: Path
    baseline_ref: str
    branch_name: str
    worktree_path: Path | None
    lock: RunLock
    checkpoints: CheckpointStore
    meta_path: Path

    def finish(self) -> str:
        """Return final diff text; does not push."""
        from codeagent.isolation.finish import format_final_diff

        return format_final_diff(self.workspace, self.baseline_ref)

    def cleanup(self) -> None:
        if self.mode == "worktree" and self.worktree_path is not None:
            run_git(
                self.git_root,
                ["worktree", "remove", "--force", str(self.worktree_path)],
                check=False,
            )
            shutil.rmtree(self.worktree_path, ignore_errors=True)
            run_git(self.git_root, ["branch", "-D", self.branch_name], check=False)
        elif self.mode == "branch":
            run_git(self.git_root, ["checkout", "-"], check=False)
            run_git(self.git_root, ["branch", "-D", self.branch_name], check=False)
        self.lock.release()


def _record_meta(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _is_dirty(repo: Path) -> bool:
    status = run_git(
        repo,
        ["status", "--porcelain", "--", ".", ":!.codeagent"],
        check=False,
    )
    return bool(status.stdout.strip())


_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _baseline_ref(repo: Path) -> str:
    head = run_git(repo, ["rev-parse", "HEAD"], check=False)
    if head.returncode == 0:
        return head.stdout.strip()
    return _EMPTY_TREE


def git_isolation_mode(settings: IsolationSettings) -> str:
    """Git worktree/branch mode; ``docker`` only affects command execution."""
    if settings.mode == "branch":
        return "branch"
    return "worktree"


def begin_isolation(
    git_root: Path,
    run_id: str,
    settings: IsolationSettings,
    *,
    on_dirty: Callable[[str], DirtyTreeChoice] | None = None,
    force_branch: bool = False,
) -> IsolationSession:
    """Create an isolated workspace; user's checkout stays on the original branch."""
    root = git_root.resolve()
    lock = RunLock.acquire(root, run_id)
    branch_name = f"codeagent/{run_id}"
    meta_path = root / ".codeagent" / "runs" / run_id / "session.json"
    user_branch = run_git(root, ["branch", "--show-current"], check=False).stdout.strip()
    mode = git_isolation_mode(settings)
    worktree_path: Path | None = None
    workspace = root

    if mode == "worktree" and not force_branch:
        wt_root = root / ".codeagent" / "worktrees" / run_id
        wt_root.parent.mkdir(parents=True, exist_ok=True)
        add = run_git(
            root,
            ["worktree", "add", "-b", branch_name, str(wt_root)],
            check=False,
        )
        if add.returncode != 0:
            mode = "branch"
        else:
            worktree_path = wt_root
            workspace = wt_root

    if mode == "branch" or force_branch:
        mode = "branch"
        if _is_dirty(root):
            prompt = "uncommitted changes in the working tree"
            choice = on_dirty(prompt) if on_dirty is not None else DirtyTreeChoice.ABORT
            if choice is DirtyTreeChoice.ABORT:
                lock.release()
                raise IsolationError(
                    "dirty working tree; stash or commit before branch-mode isolation",
                )
        run_git(root, ["checkout", "-b", branch_name], check=True)
        workspace = root

    baseline = _baseline_ref(workspace)
    checkpoints = CheckpointStore.load(root, run_id, workspace=workspace)
    _record_meta(
        meta_path,
        {
            "run_id": run_id,
            "mode": mode,
            "baseline_ref": baseline,
            "branch_name": branch_name,
            "user_branch": user_branch,
            "worktree_path": str(worktree_path) if worktree_path else None,
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    return IsolationSession(
        git_root=root,
        run_id=run_id,
        mode=mode,
        workspace=workspace,
        user_root=root,
        baseline_ref=baseline,
        branch_name=branch_name,
        worktree_path=worktree_path,
        lock=lock,
        checkpoints=checkpoints,
        meta_path=meta_path,
    )
