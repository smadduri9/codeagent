from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectedCommands:
    test: list[str] | None
    typecheck: list[str] | None
    lint: list[str] | None
    build: list[str] | None

    def as_verify_toml(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for key in ("test", "typecheck", "lint", "build"):
            val = getattr(self, key)
            if val is not None:
                out[key] = val
        return out


def detect_commands(repo_root: Path) -> DetectedCommands:
    py = repo_root / "pyproject.toml"
    test = None
    lint = None
    typecheck = None
    if py.is_file():
        text = py.read_text(encoding="utf-8")
        if "pytest" in text:
            test = ["python", "-m", "pytest", "-q"]
        if re.search(r"\[tool\.ruff\]", text):
            lint = ["python", "-m", "ruff", "check", "."]
        if re.search(r"\[tool\.mypy\]", text):
            typecheck = ["python", "-m", "mypy", "src"]
    pkg = repo_root / "package.json"
    build = None
    if pkg.is_file():
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        if isinstance(scripts, dict):
            if "test" in scripts:
                test = ["npm", "test"]
            if "lint" in scripts:
                lint = ["npm", "run", "lint"]
            if "build" in scripts:
                build = ["npm", "run", "build"]
    return DetectedCommands(test=test, typecheck=typecheck, lint=lint, build=build)
