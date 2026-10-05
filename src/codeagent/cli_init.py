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
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines: list[str] = []
    if "[model]" not in existing and "main" not in existing:
        lines.extend(
            [
                "[model]",
                '# main = "your-groq-model-id"  # or set CODEAGENT_MODEL in .env',
                "",
            ]
        )
    lines.append("[verify]")
    lines.extend(f"{k} = {json.dumps(v)}" for k, v in detected.as_verify_toml().items())
    if existing.strip():
        path.write_text(existing.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    else:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"Wrote {path}")
