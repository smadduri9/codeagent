"""Pure parts of the SWE-bench environment recipes."""

from evals.swebench import SweInstance, check_command
from evals.swebench_env import Validation, install_command, pytest_args


def _inst(repo: str, f2p: list[str], test_patch: str = "") -> SweInstance:
    return SweInstance("x", repo, "abc", "", test_patch, f2p, [])


def test_node_ids_are_used_as_given() -> None:
    inst = _inst("pytest-dev/pytest", ["testing/test_a.py::test_one"])
    assert pytest_args(inst) == ["testing/test_a.py::test_one"]


def test_bare_names_use_patched_files_and_k() -> None:
    patch = "+++ b/sympy/core/tests/test_a.py\n+++ b/sympy/core/tests/test_b.py\n+++ b/doc.rst\n"
    inst = _inst("sympy/sympy", ["test_two", "test_one"], patch)
    expected = [
        "sympy/core/tests/test_a.py",
        "sympy/core/tests/test_b.py",
        "-k",
        "test_one or test_two",
    ]
    assert pytest_args(inst) == expected
    assert check_command(inst)[4:] == expected


def test_install_recipes() -> None:
    pylint = install_command("pylint-dev/pylint", "py")
    assert "--no-build-isolation" in pylint and "py" in pylint[pylint.index("setuptools<70") :]
    assert "pytest<8" not in install_command("pytest-dev/pytest", "py")
    assert "werkzeug<3" in install_command("pallets/flask", "py")


def test_validity_needs_fail_then_pass() -> None:
    assert Validation("a", True, 1, 0).valid
    assert not Validation("a", True, 0, 0).valid  # already passing: measures nothing
    assert not Validation("a", True, 4, 0).valid  # collection error is not a failure
    assert not Validation("a", False, None, None).valid
