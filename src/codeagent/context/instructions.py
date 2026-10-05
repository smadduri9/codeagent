"""Load repository instructions and user preferences."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeagent.context.tokens import estimate_text_tokens


@dataclass(frozen=True)
class InstructionLoadResult:
    text: str
    truncated: bool
    sources: tuple[str, ...]


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def load_instructions(
    repo_root: Path,
    *,
    user_dir: Path | None = None,
    max_tokens: int,
) -> InstructionLoadResult:
    """Load CODEAGENT.md, AGENTS.md, then user preferences in order."""
    home = user_dir if user_dir is not None else Path.home() / ".codeagent"
    chunks: list[tuple[str, str]] = []
    for name in ("CODEAGENT.md", "AGENTS.md"):
        content = _read_optional(repo_root / name)
        if content:
            chunks.append((name, content))
    prefs = _read_optional(home / "preferences.md")
    if prefs:
        chunks.append(("preferences.md", prefs))
    if not chunks:
        return InstructionLoadResult(text="", truncated=False, sources=())

    parts: list[str] = []
    sources: list[str] = []
    truncated = False
    budget = max_tokens
    for source, body in chunks:
        tokens = estimate_text_tokens(body)
        if tokens <= budget:
            parts.append(f"## {source}\n\n{body}")
            sources.append(source)
            budget -= tokens
            continue
        if budget <= 0:
            truncated = True
            break
        keep_chars = max(0, budget * 4)
        snippet = body[:keep_chars]
        parts.append(f"## {source}\n\n{snippet}\n\n[instructions truncated at token cap]")
        sources.append(source)
        truncated = True
        budget = 0
        break
    return InstructionLoadResult(
        text="\n\n".join(parts),
        truncated=truncated,
        sources=tuple(sources),
    )
