import json

from codeagent.state.store import StateStore


def reconstruct_run(store: StateStore, run_id: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for event in store.list_events(run_id):
        payload = json.loads(event.payload_json) if event.payload_json else None
        out.append({"ts": event.ts, "name": event.name, "payload": payload})
    return out
