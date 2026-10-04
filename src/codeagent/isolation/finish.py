"""Final diff output after a run."""

from __future__ import annotations

from pathlib import Path

from codeagent.isolation.git_wrapper import run_git


def format_final_diff(repo: Path, baseline_ref: str) -> str:
    """Return diff stat plus patch from baseline to HEAD (no push)."""
    stat = run_git(repo, ["diff", "--stat", baseline_ref, "HEAD"], check=False)
    patch = run_git(repo, ["diff", baseline_ref, "HEAD"], check=False)
    parts: list[str] = []
    stat_body = stat.stdout.strip()
    if stat_body:
        parts.append(stat_body)
    patch_body = patch.stdout
    if patch_body:
        if parts:
            parts.append("")
        parts.append(patch_body.rstrip())
    if not parts:
        return "(no changes from baseline)\n"
    return "\n".join(parts) + "\n"
