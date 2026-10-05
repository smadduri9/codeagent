"""Git worktree isolation, checkpoints, and run locking."""

from codeagent.isolation.checkpoint import CheckpointStore, RollbackError
from codeagent.isolation.finish import format_final_diff
from codeagent.isolation.lock import RunLock, RunLockError
from codeagent.isolation.session import (
    DirtyTreeChoice,
    IsolationError,
    IsolationSession,
    begin_isolation,
)

__all__ = [
    "CheckpointStore",
    "DirtyTreeChoice",
    "IsolationError",
    "IsolationSession",
    "RollbackError",
    "RunLock",
    "RunLockError",
    "begin_isolation",
    "format_final_diff",
]
