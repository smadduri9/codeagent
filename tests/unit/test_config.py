"""Configuration tests are offline and isolated from the owner's files."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from codeagent.config import ConfigError, Price, Settings, find_git_root, load_settings


@pytest.fixture
def paths(tmp_path: Path) -> tuple[Path, Path]:
    repo, user = tmp_path / "repo", tmp_path / "user"
    (repo / ".git").mkdir(parents=True)
    user.mkdir()
    return repo, user


def write_config(directory: Path, contents: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.toml").write_text(contents)


def test_missing_files_use_documented_defaults(paths: tuple[Path, Path]) -> None:
    repo, user = paths
    settings = load_settings(repo, user_dir=user)
    assert settings.model.main is None
    assert settings.model.cheap is None
    assert settings.model.fallbacks == []
    assert settings.prices == {}
    assert settings.rate_limits == {}
    assert settings.model.base_url == "https://api.groq.com/openai/v1"
    assert settings.model.api_key_env == "GROQ_API_KEY"
    assert settings.model.profile == "free_tier"
    assert settings.limits.max_total_tokens == 150000
    assert settings.request.max_request_tokens == 6500
    assert settings.request.max_output_tokens == 1000
    assert settings.tools.max_output_chars == 8000
    assert settings.tools.read_default_lines == 120
    assert settings.tools.instructions_max_tokens == 1500
    # No rate or price can be silently invented for an unconfigured model.
    assert all(field.is_required() for field in Price.model_fields.values())


def test_each_layer_overrides_only_supplied_fields(paths: tuple[Path, Path]) -> None:
    repo, user = paths
    write_config(
        user, '[model]\nmain="user-model"\ncheap="small-model"\n[limits]\nmax_iterations=7'
    )
    first = load_settings(repo, user_dir=user)
    assert first.model.main == "user-model"
    assert first.limits.max_iterations == 7
    write_config(repo / ".codeagent", '[model]\nmain="repo-model"\n[tools]\nread_default_lines=9')
    second = load_settings(repo, user_dir=user)
    assert second.model.main == "repo-model"
    assert second.model.cheap == "small-model"
    flags: dict[str, object] = {"model": {"main": "flag-model"}}
    third = load_settings(repo, user_dir=user, overrides=flags)
    assert third.model.main == "flag-model"
    assert third.model.cheap == "small-model"
    assert third.limits.max_iterations == 7
    assert third.tools.read_default_lines == 9
    assert flags == {"model": {"main": "flag-model"}}


def test_arrays_replace_and_model_tables_merge(paths: tuple[Path, Path]) -> None:
    repo, user = paths
    write_config(
        user,
        '[model]\nfallbacks=["first"]\n[prices.test]\ninput=0.0\noutput=0.0\ncache_read=0.0\n'
        "[rate_limits.test]\nrpm=30\nrpd=1000\ntpm=8000\ntpd=200000",
    )
    write_config(repo / ".codeagent", "[model]\nfallbacks=[]\n[rate_limits.test]\nrpm=5")
    settings = load_settings(repo, user_dir=user)
    assert settings.model.fallbacks == []
    assert settings.rate_limits["test"].rpm == 5
    assert settings.rate_limits["test"].tpd == 200000
    assert settings.prices["test"].input == 0


@pytest.mark.parametrize(
    "data",
    [
        {"unknown": 1},
        {"model": {"unknown": 1}},
        {"model": {"main": " "}},
        {"model": {"provider": "unknown"}},
        {"model": {"profile": "unknown"}},
        {"model": {"api_key_env": "bad-name"}},
        {"model": {"base_url": "file:///tmp/model"}},
        {"model": {"base_url": "https://user:synthetic@example.test"}},
        {"model": {"base_url": "https://example.test?token=synthetic"}},
        {"limits": {"max_iterations": 0}},
        {"limits": {"max_iterations": True}},
        {"limits": {"max_cost_usd": float("nan")}},
        {"request": {"max_request_tokens": -1}},
        {"tools": {"read_default_lines": "120"}},
        {"permissions": {"edit_mode": "deny"}},
        {"isolation": {"mode": "unknown"}},
        {"verify": {"commands": [[]]}},
        {"verify": {"commands": ["pytest -q"]}},
        {"index": {"enabled": "false"}},
        {"rate_limits": {"test": {"rpm": 1}}},
        {"prices": {"test": {"input": -1, "output": 0, "cache_read": 0}}},
        {"prices": {"test": {"input": 0, "output": 0, "cache_read": 0, "extra": 1}}},
    ],
)
def test_invalid_values_and_unknown_keys(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(data)


def test_all_tables_from_design_load(paths: tuple[Path, Path]) -> None:
    repo, user = paths
    write_config(
        repo / ".codeagent",
        '[model]\nmain="chosen"\ncheap="smaller"\nreasoning_effort="low"\n'
        '[permissions]\nedit_mode="ask"\nextra_allow=["git status"]\n'
        'web_allowlist=["example.test"]\nsecret_paths=["private.txt"]\n'
        '[isolation]\nmode="branch"\n[verify]\ncommands=[["pytest", "-q"]]\ntimeout_s=5\n'
        "[index]\nenabled=false",
    )
    settings = load_settings(repo, user_dir=user)
    assert settings.model.main == "chosen"
    assert settings.permissions.edit_mode == "ask"
    assert settings.verify.commands == [["pytest", "-q"]]
    assert settings.isolation.mode == "branch"


@pytest.mark.parametrize("text", ["[bad", 'model="synthetic-private-value"'])
def test_diagnostics_omit_values(paths: tuple[Path, Path], text: str) -> None:
    repo, user = paths
    write_config(user, text)
    with pytest.raises(ConfigError) as error:
        load_settings(repo, user_dir=user)
    assert text not in str(error.value)
    assert "synthetic-private-value" not in str(error.value)


def test_git_root_from_nested_directory_and_worktree_marker(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: unused-test-path")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_git_root(nested) == tmp_path.resolve()


def test_outside_git_repository_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Git repository"):
        find_git_root(tmp_path)
