import json
from pathlib import Path

from codeagent.state.store import StateStore


def trace_jsonl_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / ".codeagent" / "traces" / f"{run_id}.jsonl"


def _events_from_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(
            {
                "ts": row.get("ts", ""),
                "name": row.get("name", ""),
                "payload": row.get("payload"),
            },
        )
    return out


def reconstruct_run(
    store: StateStore,
    run_id: str,
    *,
    repo_root: Path | None = None,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for event in store.list_events(run_id):
        payload = json.loads(event.payload_json) if event.payload_json else None
        out.append({"ts": event.ts, "name": event.name, "payload": payload})
    if out:
        return out
    if repo_root is not None:
        return _events_from_jsonl(trace_jsonl_path(repo_root, run_id))
    return []
