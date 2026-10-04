"""Gitignore helper tests."""

from pathlib import Path

from codeagent.tools.gitignore import is_ignored, load_gitignore_patterns


def test_load_and_match(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitignore").write_text("*.log\nbuild/\n", encoding="utf-8")
    patterns = load_gitignore_patterns(root)
    assert "*.log" in patterns
    assert is_ignored(Path("foo.log"), patterns)
    assert is_ignored(Path("build"), patterns)
    assert not is_ignored(Path("src/main.py"), patterns)
