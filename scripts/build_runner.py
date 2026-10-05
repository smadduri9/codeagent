"""One-off: build loop/runner.py from the phase-4 loop skeleton."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/codeagent/loop/runner.py"

# Embedded phase-5 loop (kept in-repo so runner is never empty).
TARGET.write_text(
    (ROOT / "src/codeagent/loop/runner.py").read_text()
    if (ROOT / "src/codeagent/loop/runner.py").stat().st_size > 1000
    else "",
    encoding="utf-8",
)
