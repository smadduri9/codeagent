"""Repository run lock to prevent concurrent agent runs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    else:
        return True


class RunLockError(RuntimeError):
    """Another run holds the lock or the lock file is invalid."""


@dataclass
class RunLock:
    path: Path
    run_id: str

    @staticmethod
    def lock_path(git_root: Path) -> Path:
        return git_root / ".codeagent" / "run.lock"

    @classmethod
    def release_stale(cls, git_root: Path, *, force: bool = False) -> bool:
        """Remove the lock when the holder PID is gone, or when ``force`` is set."""
        path = cls.lock_path(git_root)
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return True
        if force or not _pid_alive(payload.get("pid")):
            path.unlink(missing_ok=True)
            return True
        return False

    @classmethod
    def acquire(cls, git_root: Path, run_id: str) -> RunLock:
        path = cls.lock_path(git_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise RunLockError("run lock is present but unreadable") from None
            if not _pid_alive(payload.get("pid")):
                path.unlink(missing_ok=True)
            else:
                other = payload.get("run_id", "unknown")
                raise RunLockError(f"another run is active: {other}")
        payload = {"run_id": run_id, "pid": os.getpid()}
        path.write_text(json.dumps(payload), encoding="utf-8")
        return cls(path=path, run_id=run_id)

    def release(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.path.unlink(missing_ok=True)
            return
        if payload.get("run_id") == self.run_id:
            self.path.unlink(missing_ok=True)
