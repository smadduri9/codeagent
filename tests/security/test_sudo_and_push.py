"""Security: forbidden shell commands."""

from pathlib import Path

from codeagent.config import Settings
from codeagent.permissions import Deny, classify_shell


def test_sudo_cannot_execute(tmp_path: Path) -> None:
    decision = classify_shell("sudo rm -rf /", tmp_path, Settings().permissions)
    assert isinstance(decision, Deny)


def test_force_push_denied_by_default(tmp_path: Path) -> None:
    decision = classify_shell(
        "git push --force origin main",
        tmp_path,
        Settings().permissions,
    )
    assert isinstance(decision, Deny)
