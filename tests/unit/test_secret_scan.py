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


@pytest.mark.parametrize("name", ["API_KEY", "TOKEN", "SECRET", "PASSWORD"])
@pytest.mark.parametrize("prefix", ["", "SERVICE_"])
@pytest.mark.parametrize("style", ["{}={}", "export {}='{}'", '  {} = "{}"'])
def test_credential_assignments_fail_without_echo(
    tmp_path: Path, name: str, prefix: str, style: str
) -> None:
    value = "synthetic-assignment-value"
    content = style.format(prefix + name, value)
    result = scan_fixture(tmp_path, "fixture.txt", content)
    assert result.returncode == 1
    assert "contents withheld" in result.stdout
    assert value not in result.stdout + result.stderr


@pytest.mark.parametrize("location", ["index", "worktree"])
def test_bare_assignment_in_either_tracked_copy(tmp_path: Path, location: str) -> None:
    value = "synthetic-copy-value"
    assignment = "API_KEY=" + value
    scan_fixture(tmp_path, "fixture.txt", assignment if location == "index" else "clean text")
    (tmp_path / "fixture.txt").write_text(assignment if location == "worktree" else "clean text")
    result = subprocess.run(
        [str(SCANNER)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert value not in result.stdout + result.stderr


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


@pytest.mark.parametrize("path", [".env.example", "nested/.env.example"])
@pytest.mark.parametrize("location", ["index", "worktree"])
@pytest.mark.parametrize("name", ["API_KEY", "TOKEN", "SECRET", "PASSWORD", "GROQ_API_KEY"])
@pytest.mark.parametrize("style", ["{}={}", "export {}='{}'", '  {} = "{}"'])
def test_example_assignments_in_either_tracked_copy(
    tmp_path: Path, path: str, location: str, name: str, style: str
) -> None:
    value = "synthetic-example-credential"
    clean = "GROQ_API_KEY=" + "your_groq_key_here\n"
    content = clean + style.format(name, value) + "\n" + clean
    scan_fixture(tmp_path, path, content if location == "index" else clean)
    (tmp_path / path).write_text(content if location == "worktree" else clean)
    result = subprocess.run(
        [str(SCANNER)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert "contents withheld" in result.stdout
    assert value not in result.stdout + result.stderr


@pytest.mark.parametrize("path", [".env.example", "nested/.env.example"])
@pytest.mark.parametrize("value", ["your_groq_key_here", "your-key-here"])
@pytest.mark.parametrize("quote", ["", "'", '"'])
def test_example_known_placeholders(tmp_path: Path, path: str, value: str, quote: str) -> None:
    content = "# Example configuration\nexport GROQ_API_KEY = " + quote + value + quote + "\n"
    assert scan_fixture(tmp_path, path, content).returncode == 0


@pytest.mark.parametrize(
    "value",
    [
        "your_groq_key_here-synthetic-suffix",
        "synthetic-prefix-your-key-here",
        "your_groq_key_here synthetic-trailing-value",
        "'your-key-here' synthetic-trailing-value",
        "'your-key-here\"",
    ],
)
def test_example_placeholder_must_be_entire_value(tmp_path: Path, value: str) -> None:
    result = scan_fixture(tmp_path, ".env.example", "API_KEY=" + value)
    assert result.returncode == 1
    assert value not in result.stdout + result.stderr


@pytest.mark.parametrize("value", ["your_groq_key_here", "your-key-here"])
def test_placeholder_exemption_is_only_for_examples(tmp_path: Path, value: str) -> None:
    assert scan_fixture(tmp_path, "fixture.txt", "API_KEY=" + value).returncode == 1
