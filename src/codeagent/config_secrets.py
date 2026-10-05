"""Explicit, non-mutating API-key loading, before creating any worktree."""

import os
import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import SecretStr

from codeagent.config import ConfigError, find_git_root


def _read_key(path: Path, variable: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        raise ConfigError("Cannot read API-key file") from None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
            raise ConfigError("Invalid API-key file: expected KEY=value lines")
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigError("Invalid API-key file: unmatched quote")
            value = value[1:-1]
        if name.strip() == variable and value.strip():
            return value
    return None


def resolve_env_value(
    variable: str,
    start_dir: Path,
    *,
    user_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve a variable from the process environment, then git-root and user `.env` files."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
        raise ConfigError("Invalid environment variable name")
    environment = os.environ if environ is None else environ
    value = environment.get(variable)
    if value and value.strip():
        return value.strip()
    root = find_git_root(start_dir)
    home = user_dir if user_dir is not None else Path.home() / ".codeagent"
    for path in (root / ".env", home / ".env"):
        value = _read_key(path, variable)
        if value is not None:
            return value
    return None


def load_api_key(
    api_key_env: str,
    start_dir: Path,
    *,
    user_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> SecretStr:
    """Resolve process, git-root, then user key; never export or interpolate it."""
    value = resolve_env_value(api_key_env, start_dir, user_dir=user_dir, environ=environ)
    if value is None:
        raise ConfigError(
            f"Missing API key: set {api_key_env} in the environment or an API-key file"
        )
    return SecretStr(value)
