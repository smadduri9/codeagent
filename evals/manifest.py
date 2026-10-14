"""Run manifest for eval output: what was run, on which code, with which prompt."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codeagent.config import Settings
from codeagent.context.prompts import load_system_prompt, prompt_hash


def _git_commit(cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "unknown"


def build_manifest(
    *,
    task_ids: list[str],
    mode: str,
    repeats: int,
    repo_root: Path,
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    config_sha = hashlib.sha256(Settings().model_dump_json().encode("utf-8")).hexdigest()
    return {
        "tasks": task_ids,
        "mode": mode,
        "repeats": repeats,
        "model": model or ("replay" if mode == "replay" else "unspecified"),
        "provider": provider or ("fake" if mode == "replay" else "unspecified"),
        "git_commit": _git_commit(repo_root),
        "config_sha256": config_sha,
        "prompt_hash": prompt_hash(load_system_prompt()),
        "started_at": datetime.now(UTC).isoformat(),
    }


def write_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
