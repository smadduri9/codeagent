import json
import tomllib
from pathlib import Path

import typer
from rich.console import Console

from codeagent.config import find_git_root
from codeagent.verification.detect import detect_commands

console = Console()


def init_command() -> None:
    root = find_git_root(Path.cwd())
    path = root / ".codeagent" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        data = tomllib.loads(existing)
    except tomllib.TOMLDecodeError as exc:
        console.print(f"[red]Cannot parse {path}: {exc}. Fix or remove it, then rerun.[/red]")
        raise typer.Exit(code=1) from exc
    if "verify" in data:
        console.print(f"{path} already has a [verify] table; left unchanged")
        return
    detected = detect_commands(root)
    lines: list[str] = []
    if "model" not in data:
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
