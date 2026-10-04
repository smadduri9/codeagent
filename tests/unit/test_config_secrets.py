"""Only synthetic values in temporary directories reach the key loader."""

from pathlib import Path

import pytest

from codeagent.config import ConfigError
from codeagent.config_secrets import load_api_key

VARIABLE = "TEST_PROVIDER_KEY"


@pytest.fixture
def paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo, user = tmp_path / "repo", tmp_path / "user"
    nested = repo / "nested"
    (repo / ".git").mkdir(parents=True)
    nested.mkdir()
    user.mkdir()
    return repo, user, nested


def test_process_then_root_then_user_precedence(paths: tuple[Path, Path, Path]) -> None:
    repo, user, nested = paths
    (repo / ".env").write_text(f"{VARIABLE}=root-synthetic")
    (user / ".env").write_text(f"{VARIABLE}=user-synthetic")
    (nested / ".env").write_text(f"{VARIABLE}=wrong-directory")
    environ = {VARIABLE: "process-synthetic"}
    assert load_api_key(VARIABLE, nested, user_dir=user, environ=environ).get_secret_value() == (
        "process-synthetic"
    )
    assert environ == {VARIABLE: "process-synthetic"}
    assert load_api_key(VARIABLE, nested, user_dir=user, environ={}).get_secret_value() == (
        "root-synthetic"
    )
    (repo / ".env").unlink()
    assert load_api_key(VARIABLE, nested, user_dir=user, environ={}).get_secret_value() == (
        "user-synthetic"
    )


def test_process_short_circuits_files(paths: tuple[Path, Path, Path]) -> None:
    repo, user, nested = paths
    (repo / ".env").write_text("invalid file, should not be read")
    key = load_api_key(VARIABLE, nested, user_dir=user, environ={VARIABLE: "synthetic"})
    assert key.get_secret_value() == "synthetic"


def test_empty_values_fall_through(paths: tuple[Path, Path, Path]) -> None:
    repo, user, nested = paths
    (repo / ".env").write_text(f'{VARIABLE}=""')
    (user / ".env").write_text(f"{VARIABLE}=synthetic")
    key = load_api_key(VARIABLE, nested, user_dir=user, environ={VARIABLE: " "})
    assert key.get_secret_value() == "synthetic"


def test_key_is_not_printed_logged_or_exported(
    paths: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    repo, user, nested = paths
    monkeypatch.delenv(VARIABLE, raising=False)
    value = "only-a-synthetic-fixture"
    (repo / ".env").write_text(f"{VARIABLE}={value}")
    key = load_api_key(VARIABLE, nested, user_dir=user)
    assert key.get_secret_value() == value
    assert value not in str(key) + repr(key)
    captured = capsys.readouterr()
    assert captured.out == captured.err == caplog.text == ""
    assert VARIABLE not in os.environ


def test_missing_key_names_variable(paths: tuple[Path, Path, Path]) -> None:
    _, user, nested = paths
    with pytest.raises(ConfigError, match=f"Missing API key: set {VARIABLE}"):
        load_api_key(VARIABLE, nested, user_dir=user, environ={})


@pytest.mark.parametrize(
    "value", ["export TEST_PROVIDER_KEY=synthetic", "bad line", "KEY='unclosed"]
)
def test_malformed_file_has_safe_error(paths: tuple[Path, Path, Path], value: str) -> None:
    repo, user, nested = paths
    (repo / ".env").write_text(value)
    with pytest.raises(ConfigError) as error:
        load_api_key(VARIABLE, nested, user_dir=user, environ={})
    assert value not in str(error.value)


def test_quotes_comments_and_no_expansion(paths: tuple[Path, Path, Path]) -> None:
    repo, user, nested = paths
    (repo / ".env").write_text(f"# comment\n\n {VARIABLE} = '${{UNEXPANDED}}'\n")
    assert load_api_key(VARIABLE, nested, user_dir=user, environ={}).get_secret_value() == (
        "${UNEXPANDED}"
    )
