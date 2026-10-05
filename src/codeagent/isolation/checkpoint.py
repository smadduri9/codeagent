"""Checkpoint commits and rollback helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from codeagent.isolation.git_wrapper import GitCommandError, run_git

_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class RollbackError(RuntimeError):
    """Rollback could not be applied."""


@dataclass
class CheckpointRecord:
    label: str
    git_ref: str
    created_at: str


@dataclass
class CheckpointStore:
    run_id: str
    git_root: Path
    repo: Path
    path: Path
    records: list[CheckpointRecord] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        git_root: Path,
        run_id: str,
        *,
        workspace: Path | None = None,
    ) -> CheckpointStore:
        path = git_root / ".codeagent" / "runs" / run_id / "checkpoints.json"
        records: list[CheckpointRecord] = []
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data.get("checkpoints", []):
                records.append(
                    CheckpointRecord(
                        label=item["label"],
                        git_ref=item["git_ref"],
                        created_at=item["created_at"],
                    ),
                )
        return cls(
            run_id=run_id,
            git_root=git_root,
            repo=workspace or git_root,
            path=path,
            records=records,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "checkpoints": [
                {"label": r.label, "git_ref": r.git_ref, "created_at": r.created_at}
                for r in self.records
            ],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(self, label: str) -> CheckpointRecord:
        message = f"codeagent: checkpoint {label}"
        run_git(self.repo, ["add", "-A"], check=True)
        staged = run_git(self.repo, ["diff", "--cached", "--quiet"], check=False)
        if staged.returncode == 0:
            head = run_git(self.repo, ["rev-parse", "HEAD"], check=False)
            ref = head.stdout.strip() if head.returncode == 0 else _EMPTY_TREE_SHA
        else:
            run_git(self.repo, ["commit", "-m", message], check=True)
            ref = run_git(self.repo, ["rev-parse", "HEAD"], check=True).stdout.strip()
        created = datetime.now(UTC).isoformat()
        record = CheckpointRecord(label=label, git_ref=ref, created_at=created)
        self.records.append(record)
        self.save()
        return record

    def rollback_to(self, label: str | None) -> str:
        target_ref: str
        if label is None:
            if not self.records:
                raise RollbackError("no checkpoints recorded for this run")
            target_ref = self.records[0].git_ref
        else:
            matches = [r for r in self.records if r.label == label]
            if not matches:
                raise RollbackError(f"unknown checkpoint label: {label}")
            target_ref = matches[-1].git_ref
        try:
            run_git(self.repo, ["reset", "--hard", target_ref], check=True)
        except GitCommandError as exc:
            raise RollbackError(str(exc)) from exc
        return target_ref
