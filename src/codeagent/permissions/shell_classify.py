"""Classify shell segments into allow, ask, or deny."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from codeagent.config import PermissionSettings
from codeagent.permissions.rules import extract_redirect_paths, path_write_decision
from codeagent.permissions.shell_parse import parse_shell, segment_argv
from codeagent.permissions.types import Allow, Ask, Decision, Deny, RiskLevel, strictest

_READ_ONLY_COMMANDS = frozenset(
    {
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "rg",
        "grep",
        "pwd",
        "which",
    },
)
_GIT_READ_SUBCOMMANDS = frozenset({"status", "diff", "log", "show", "branch"})
_ASK_COMMANDS = frozenset(
    {
        "rm",
        "mv",
        "pip",
        "pip3",
        "npm",
        "pnpm",
        "yarn",
        "brew",
        "apt",
        "apt-get",
        "docker",
        "kill",
        "curl",
        "wget",
        "ssh",
        "scp",
    },
)

_DENY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\brm\s+-rf\s+/"), "rm -rf /"),
    (re.compile(r"\brm\s+-rf\s+~"), "rm -rf ~"),
    (re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*\s+/"), "rm -rf /"),
    (re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*\s+~"), "rm -rf ~"),
    (re.compile(r"\bchmod\s+-R\s+777\b"), "chmod -R 777"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*sh\b"), "curl|wget | sh"),
    (re.compile(r"\bgit\s+push\b[^;\n]*--force\b"), "git push --force"),
    (re.compile(r"\bgit\s+push\b[^;\n]*-f\b"), "git push --force"),
    (re.compile(r"\bmkfs\b"), "mkfs"),
    (re.compile(r"\bdd\b[^;\n]*\bof=/dev/"), "dd to device"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "fork bomb"),
)


def _normalize(segment: str) -> str:
    return " ".join(segment.split())


def _command_name(argv: list[str]) -> str | None:
    if not argv:
        return None
    token = argv[0]
    return Path(token).name


def _classify_find(argv: list[str]) -> Decision:
    for arg in argv[1:]:
        if arg in {"-delete", "-exec"}:
            return Ask("find with delete or exec", risk_level=RiskLevel.DESTRUCTIVE)
    return Allow(risk_level=RiskLevel.READ_ONLY)


def _classify_git(argv: list[str]) -> Decision:
    if len(argv) < 2:
        return Ask("unknown git invocation", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    sub = argv[1]
    if sub in _GIT_READ_SUBCOMMANDS:
        return Allow(risk_level=RiskLevel.READ_ONLY)
    if sub == "push":
        return Ask("git push", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    if sub == "reset" and any("hard" in a for a in argv[2:]):
        return Ask("git reset --hard", risk_level=RiskLevel.DESTRUCTIVE)
    if sub == "clean":
        return Ask("git clean", risk_level=RiskLevel.DESTRUCTIVE)
    if sub == "checkout" and "--" in argv and "." in argv:
        return Ask("git checkout -- .", risk_level=RiskLevel.DESTRUCTIVE)
    return Ask("unknown git command", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)


def classify_segment(segment: str, settings: PermissionSettings) -> Decision:
    normalized = _normalize(segment)
    for pattern, label in _DENY_PATTERNS:
        if pattern.search(normalized):
            return Deny(label, risk_level=RiskLevel.FORBIDDEN)

    argv = segment_argv(segment)
    name = _command_name(argv)
    if name is None:
        return Ask("empty command", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)

    extra = {Path(item).name for item in settings.extra_allow}
    if name in extra:
        return Allow(risk_level=RiskLevel.READ_ONLY)

    if name in _READ_ONLY_COMMANDS:
        return Allow(risk_level=RiskLevel.READ_ONLY)
    if name == "find":
        return _classify_find(argv)
    if name == "git":
        return _classify_git(argv)
    if name in _ASK_COMMANDS:
        return Ask(f"{name} requires approval", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    if name == "mv":
        return Ask("mv requires approval", risk_level=RiskLevel.DESTRUCTIVE)

    return Ask("unknown command", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)


def _deny_on_full_command(command: str) -> Decision | None:
    normalized = _normalize(command)
    for pattern, label in _DENY_PATTERNS:
        if pattern.search(normalized):
            return Deny(label, risk_level=RiskLevel.FORBIDDEN)
    return None


def classify_shell(
    command: str,
    workspace: Path,
    settings: PermissionSettings,
) -> Decision:
    full_deny = _deny_on_full_command(command)
    if full_deny is not None:
        return full_deny
    parsed = parse_shell(command)
    if parsed.issues:
        detail = parsed.issues[0].detail
        return Ask(f"shell parse hazard: {detail}", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)

    decisions: list[Decision] = []
    for segment in parsed.segments:
        decisions.append(classify_segment(segment, settings))
        for target in extract_redirect_paths(segment):
            if target not in {"/dev/null", "/dev/stderr", "/dev/stdout"}:
                decisions.append(
                    path_write_decision(workspace, target, settings),
                )
    return strictest(*decisions) if decisions else Ask("empty shell command")


def classify_argv(
    argv: list[str],
    settings: PermissionSettings,
) -> Decision:
    """Classify a no-shell argv list (run_command)."""
    if not argv:
        return Ask("empty argv", risk_level=RiskLevel.EXTERNAL_SIDE_EFFECT)
    segment = " ".join(shlex.quote(str(part)) for part in argv)
    return classify_segment(segment, settings)
