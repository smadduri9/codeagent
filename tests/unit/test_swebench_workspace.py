"""SWE-bench workspace preparation, against a local repository only."""

import subprocess
from pathlib import Path

import pytest

from evals import swebench
from evals.swebench import SweInstance, prepare_workspace


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _make_upstream(root: Path) -> tuple[Path, str]:
    """A local repo with one commit, plus a test patch that adds a test file."""
    repo = root / "upstream"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "T")
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    return repo, base


_PATCH = """diff --git a/test_new.py b/test_new.py
new file mode 100644
--- /dev/null
+++ b/test_new.py
@@ -0,0 +1,2 @@
+def test_added():
+    assert True
"""


def test_prepares_worktree_at_base_commit_with_patch_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, base = _make_upstream(tmp_path)
    monkeypatch.setattr(swebench, "repo_url", lambda repo: str(upstream))
    inst = SweInstance(
        instance_id="demo__upstream-1",
        repo="demo/upstream",
        base_commit=base,
        problem_statement="",
        test_patch=_PATCH,
        fail_to_pass=["test_new.py::test_added"],
        pass_to_pass=[],
    )
    cache = tmp_path / "cache"
    workspace = prepare_workspace(inst, cache)
    assert (workspace / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (workspace / "test_new.py").is_file()
    assert _git(workspace, "rev-parse", "HEAD") == base


def test_second_call_reuses_the_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream, base = _make_upstream(tmp_path)
    monkeypatch.setattr(swebench, "repo_url", lambda repo: str(upstream))
    inst = SweInstance(
        instance_id="demo__upstream-2",
        repo="demo/upstream",
        base_commit=base,
        problem_statement="",
        test_patch="",
        fail_to_pass=[],
        pass_to_pass=[],
    )
    cache = tmp_path / "cache"
    first = prepare_workspace(inst, cache)
    clone_marker = cache / "demo__upstream" / ".git"
    assert clone_marker.exists()
    again = prepare_workspace(
        SweInstance(**{**inst.__dict__, "instance_id": "demo__upstream-3"}),
        cache,
    )
    assert again != first
    assert (again / "app.py").is_file()
