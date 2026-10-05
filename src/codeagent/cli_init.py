import json
from pathlib import Path

from rich.console import Console

from codeagent.config import find_git_root
from codeagent.verification.detect import detect_commands

console = Console()


def init_command() -> None:
    root = find_git_root(Path.cwd())
    detected = detect_commands(root)
    path = root / ".codeagent" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[verify]"] + [f"{k} = {json.dumps(v)}" for k, v in detected.as_verify_toml().items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"Wrote {path}")
