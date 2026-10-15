"""SWE-bench live runner helpers (no model calls)."""

import subprocess
from pathlib import Path

from evals.swebench import SweInstance
from evals.swebench_live import (
    eval_settings,
    goal_text,
    patched_test_files,
    restore_and_apply_tests,
)

_PATCH = """diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1 +1,2 @@
 def test_old(): pass
+def test_new(): pass
diff --git a/tests/test_b.py b/tests/test_b.py
new file mode 100644
--- /dev/null
+++ b/tests/test_b.py
@@ -0,0 +1 @@
+def test_b(): pass
"""


def _repo(path: Path) -> None:
    (path / "tests").mkdir(parents=True)
    (path / "tests" / "test_a.py").write_text("def test_old(): pass\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=T", "commit", "-qm", "base"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True)


def test_patched_test_files() -> None:
    assert patched_test_files(_PATCH) == ["tests/test_a.py", "tests/test_b.py"]


def test_agent_test_edits_are_reverted_before_the_patch(tmp_path: Path) -> None:
    _repo(tmp_path)
    (tmp_path / "tests" / "test_a.py").write_text("def test_old(): assert True  # agent\n")
    (tmp_path / "tests" / "test_b.py").write_text("def test_b(): assert 0  # agent-created\n")
    assert restore_and_apply_tests(tmp_path, _PATCH)
    assert (
        tmp_path / "tests" / "test_a.py"
    ).read_text() == "def test_old(): pass\ndef test_new(): pass\n"
    assert (tmp_path / "tests" / "test_b.py").read_text() == "def test_b(): pass\n"


def test_goal_hides_tests_and_names_the_repo() -> None:
    inst = SweInstance("i", "demo/repo", "abc", "Bug: x is wrong.", "secret test patch", ["t"], [])
    text = goal_text(inst)
    assert "demo/repo" in text and "Bug: x is wrong." in text
    assert "secret test patch" not in text


def test_eval_settings_allow_only_python_and_pytest() -> None:
    settings = eval_settings(max_iterations=7)
    assert settings.permissions.extra_allow == ["python", "pytest"]
    assert settings.limits.max_iterations == 7


def test_eval_approver_allows_only_python_and_pytest_commands() -> None:
    from codeagent.permissions.types import Allow, Ask, Deny
    from codeagent.providers.base import ToolCall
    from evals.swebench_live import EvalApprover

    approver = EvalApprover()
    ask = Ask("needs approval")
    py = ToolCall(id="1", name="run_command", args={"argv": ["python", "-m", "pytest", "t.py"]})
    pt = ToolCall(id="2", name="run_command", args={"argv": ["/env/bin/pytest", "-q"]})
    curl = ToolCall(id="3", name="run_command", args={"argv": ["curl", "http://x"]})
    write = ToolCall(id="4", name="write_file", args={"path": "a.py", "content": "x"})
    assert isinstance(approver.resolve(py, ask), Allow)
    assert isinstance(approver.resolve(pt, ask), Allow)
    assert isinstance(approver.resolve(curl, ask), Deny)
    assert isinstance(approver.resolve(write, ask), Deny)
    assert approver.choice == "session"


def test_compaction_threshold_is_configurable() -> None:
    assert eval_settings(max_iterations=5).request.max_request_tokens == 30_000
    assert (
        eval_settings(max_iterations=5, max_request_tokens=8_000).request.max_request_tokens
        == 8_000
    )


def test_thinking_off_setting_per_model() -> None:
    from evals.spend import HAIKU, SONNET
    from evals.swebench_live import thinking_off

    assert thinking_off(HAIKU) == {"type": "disabled"}
    # Sonnet 5.5 rejects "disabled"; "between_tools" turns thinking off there.
    assert thinking_off(SONNET) == {"type": "between_tools"}
