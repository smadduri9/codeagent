"""Prompt file loading and hashing."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=4)
def load_system_prompt() -> str:
    return (files("codeagent") / "prompts" / "system.md").read_text(encoding="utf-8")


@lru_cache(maxsize=4)
def load_summarize_prompt() -> str:
    return (files("codeagent") / "prompts" / "summarize.md").read_text(encoding="utf-8")


def prompt_hash(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:16]
