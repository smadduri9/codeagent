"""`codeagent init` writes a loadable config and is safe to run twice."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codeagent.cli import app


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    monkeypatch.chdir(repo)
    return repo


def _config(repo: Path) -> Path:
    return repo / ".codeagent" / "config.toml"


def test_init_writes_parseable_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0
    assert "verify" in tomllib.loads(_config(repo).read_text(encoding="utf-8"))


def test_init_twice_keeps_config_parseable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    assert CliRunner().invoke(app, ["init"]).exit_code == 0
    first = _config(repo).read_text(encoding="utf-8")
    second_run = CliRunner().invoke(app, ["init"])
    assert second_run.exit_code == 0
    assert _config(repo).read_text(encoding="utf-8") == first
    tomllib.loads(first)


def test_init_keeps_an_existing_verify_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    _config(repo).parent.mkdir()
    original = '[verify]\ntest = ["make", "test"]\n'
    _config(repo).write_text(original, encoding="utf-8")
    assert CliRunner().invoke(app, ["init"]).exit_code == 0
    assert _config(repo).read_text(encoding="utf-8") == original


def test_init_refuses_to_touch_a_broken_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    _config(repo).parent.mkdir()
    broken = "[verify\n"
    _config(repo).write_text(broken, encoding="utf-8")
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 1
    assert _config(repo).read_text(encoding="utf-8") == broken


def test_init_adds_verify_to_a_config_without_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    _config(repo).parent.mkdir()
    _config(repo).write_text('[model]\nmain = "some-model"\n', encoding="utf-8")
    assert CliRunner().invoke(app, ["init"]).exit_code == 0
    data = tomllib.loads(_config(repo).read_text(encoding="utf-8"))
    assert data["model"]["main"] == "some-model"
    assert "verify" in data
