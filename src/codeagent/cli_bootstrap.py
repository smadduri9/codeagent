"""Ensure a Git repo is ready for interactive CodeAgent sessions."""

from __future__ import annotations

import json
from pathlib import Path

from codeagent.config import find_git_root, load_settings
from codeagent.config_secrets import load_api_key
from codeagent.providers.factory import resolve_run_model
from codeagent.verification.detect import detect_commands


def ensure_workspace(cwd: Path) -> Path:
    """Create `.codeagent/` basics when missing; return the git root."""
    repo_root = find_git_root(cwd)
    config_path = repo_root / ".codeagent" / "config.toml"
    if config_path.exists():
        return repo_root

    detected = detect_commands(repo_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[model]",
        '# main = "your-groq-model-id"  # or set CODEAGENT_MODEL in .env',
        "",
        "[verify]",
    ]
    lines.extend(f"{k} = {json.dumps(v)}" for k, v in detected.as_verify_toml().items())
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return repo_root


def validate_live_run(cwd: Path) -> None:
    """Raise ConfigError when model or API key is missing for a live provider."""
    settings = load_settings(cwd)
    resolve_run_model(settings)
    load_api_key(settings.model.api_key_env, cwd)
