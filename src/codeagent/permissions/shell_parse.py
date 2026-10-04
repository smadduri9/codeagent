"""Parse shell command strings into segments (no execution)."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShellParseIssue:
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class ShellParseResult:
    segments: tuple[str, ...]
    issues: tuple[ShellParseIssue, ...]


_SPLIT_RE = re.compile(r"\s*(;|&&|\|\||\||&)\s*")
_HEREDOC_RE = re.compile(r"<<\s*['\"]?(\w+)['\"]?")
_SUBST_RE = re.compile(r"\$\(|`|<\(")
_EVAL_RE = re.compile(r"\beval\b")


def _scan_issues(command: str) -> list[ShellParseIssue]:
    issues: list[ShellParseIssue] = []
    if _SUBST_RE.search(command):
        issues.append(ShellParseIssue("substitution", "command substitution"))
    if _HEREDOC_RE.search(command):
        issues.append(ShellParseIssue("heredoc", "heredoc"))
    if _EVAL_RE.search(command):
        issues.append(ShellParseIssue("eval", "eval"))
    try:
        shlex.split(command, posix=True)
    except ValueError as exc:
        issues.append(ShellParseIssue("parse", str(exc)))
    return issues


_DELIMITERS = frozenset({";", "&&", "||", "|", "&"})


def split_segments(command: str) -> tuple[str, ...]:
    """Split on ``;``, ``&&``, ``||``, ``|``, and background ``&``."""
    stripped = command.strip()
    if not stripped:
        return ()
    parts = _SPLIT_RE.split(stripped)
    segments = [part.strip() for part in parts if part.strip() and part.strip() not in _DELIMITERS]
    return tuple(segments) if segments else (stripped,)


def parse_shell(command: str) -> ShellParseResult:
    issues = tuple(_scan_issues(command))
    segments = split_segments(command)
    return ShellParseResult(segments=segments or (command.strip(),), issues=issues)


def segment_argv(segment: str) -> list[str]:
    """Tokenize one segment; empty list on failure."""
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return []
