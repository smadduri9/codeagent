"""Use temporary repositories and synthetic values, never real credentials."""

import subprocess
from pathlib import Path

import pytest

SCANNER = Path(__file__).resolve().parents[2] / "scripts" / "scan_secrets.sh"


def scan_fixture(tmp_path: Path, name: str, content: str) -> subprocess.CompletedProcess[str]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", "--", name], cwd=tmp_path, check=True)
    return subprocess.run([str(SCANNER)], cwd=tmp_path, capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    "content",
    [
        "gsk" + "_" + "x" * 40,
        "sk" + "-" + "x" * 40,
        "sk" + "-ant-" + "x" * 40,
        "-----BEGIN " + "RSA PRIVATE KEY-----",
        "SERVICE_API_KEY=" + "fake-value-for-test",
    ],
)
def test_planted_secret_fails_without_echo(tmp_path: Path, content: str) -> None:
    result = scan_fixture(tmp_path, "fixture.txt", content)
    assert result.returncode == 1
    assert "contents withheld" in result.stdout
    assert content not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "name", [".env", ".env.local", ".codeagent/state", ".autobuild/log", "a.db"]
)
def test_forbidden_tracked_paths(tmp_path: Path, name: str) -> None:
    assert scan_fixture(tmp_path, name, "safe text").returncode == 1


def test_clean_repository_and_untracked_secret(tmp_path: Path) -> None:
    assert scan_fixture(tmp_path, "readme.txt", "ordinary text").returncode == 0
    (tmp_path / ".env").write_text("gsk" + "_" + "x" * 40)
    result = subprocess.run([str(SCANNER)], cwd=tmp_path, capture_output=True, check=False)
    assert result.returncode == 0


def test_index_secret_cannot_be_hidden_by_worktree(tmp_path: Path) -> None:
    assert scan_fixture(tmp_path, "fixture.txt", "gsk" + "_" + "x" * 40).returncode == 1
    (tmp_path / "fixture.txt").write_text("clean replacement")
    result = subprocess.run([str(SCANNER)], cwd=tmp_path, capture_output=True, check=False)
    assert result.returncode == 1


def test_example_allows_placeholder_but_rejects_key(tmp_path: Path) -> None:
    assert scan_fixture(tmp_path, ".env.example", "GROQ_API_KEY=your-key-here").returncode == 0
    assert scan_fixture(tmp_path, ".env.example", "gsk" + "_" + "x" * 40).returncode == 1
