"""Per-task environments for the SWE-bench subset, built with uv. Local use only.

Each task gets its own virtual environment under .codeagent/swebench/envs/<id>.
A task is valid when its failing tests fail before the reference fix (pytest exit 1)
and pass after it (exit 0). Recipes below are the ones that validated 30/30 tasks.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.swebench import SweInstance

PYTHON_VERSION = {"pallets/flask": "3.11"}
DEFAULT_PYTHON = "3.9"
EXTRA_PINS: dict[str, list[str]] = {
    "pallets/flask": ["werkzeug<3"],
    "pylint-dev/pylint": ["py"],
    "sympy/sympy": ["mpmath==1.3.0"],
    "sphinx-doc/sphinx": [
        "Jinja2<3.0",
        "markupsafe<=2.0.1",
        "alabaster==0.7.11",
        "docutils<0.18",
        "sphinxcontrib-applehelp<1.0.8",
        "sphinxcontrib-devhelp<1.0.6",
        "sphinxcontrib-htmlhelp<2.0.5",
        "sphinxcontrib-serializinghtml<1.1.10",
        "sphinxcontrib-qthelp<1.0.7",
        "html5lib",
        "cython",
    ],
}


def install_command(repo: str, python: str) -> list[str]:
    """uv command that installs the checked-out project and its test needs."""
    flags = ["--no-build-isolation"] if repo == "pylint-dev/pylint" else []
    pins = [] if repo == "pytest-dev/pytest" else ["pytest<8"]
    return [
        "uv",
        "pip",
        "install",
        "-q",
        "--python",
        python,
        *flags,
        "-e",
        ".",
        *pins,
        "setuptools<70",
        *EXTRA_PINS.get(repo, []),
    ]


def pytest_args(inst: SweInstance) -> list[str]:
    """Node ids when the dataset gives them; for bare names (sympy), patched files plus -k."""
    if all("::" in t or "/" in t for t in inst.fail_to_pass):
        return list(inst.fail_to_pass)
    files = [
        line[len("+++ b/") :]
        for line in inst.test_patch.splitlines()
        if line.startswith("+++ b/") and line.endswith(".py")
    ]
    return [*files, "-k", " or ".join(sorted(set(inst.fail_to_pass)))]


@dataclass(frozen=True)
class Validation:
    instance_id: str
    install: bool
    before_exit: int | None
    after_exit: int | None

    @property
    def valid(self) -> bool:
        return self.install and self.before_exit == 1 and self.after_exit == 0


def _run(cmd: list[str], cwd: Path, stdin: str | None = None) -> int:
    done = subprocess.run(
        cmd, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=900, check=False
    )
    return done.returncode


def build_env(inst: SweInstance, workspace: Path, env_dir: Path) -> Path:
    """Create the task's environment if missing and install the project. Returns its python."""
    python = env_dir / "bin" / "python"
    if not python.exists():
        version = PYTHON_VERSION.get(inst.repo, DEFAULT_PYTHON)
        _run(["uv", "venv", "-q", "--python", version, str(env_dir)], workspace)
    _run(
        ["uv", "pip", "install", "-q", "--python", str(python), "setuptools<70", "wheel"], workspace
    )
    if _run(install_command(inst.repo, str(python)), workspace) != 0:
        raise RuntimeError(f"install failed for {inst.instance_id}")
    return python


def validate(inst: SweInstance, workspace: Path, env_dir: Path, gold_patch: str) -> Validation:
    """Workspace must be at base_commit with no patches applied."""
    try:
        python = build_env(inst, workspace, env_dir)
    except RuntimeError:
        return Validation(inst.instance_id, False, None, None)
    test = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", *pytest_args(inst)]
    _run(["git", "apply", "-"], workspace, stdin=inst.test_patch)
    before = _run(test, workspace)
    _run(["git", "apply", "-"], workspace, stdin=gold_patch)
    after = _run(test, workspace)
    return Validation(inst.instance_id, True, before, after)


def gold_patches(jsonl_path: Path) -> dict[str, Any]:
    """Reference fixes by instance id. Used only for validation, never shown to the agent."""
    out: dict[str, Any] = {}
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[str(row["instance_id"])] = row["patch"]
    return out
