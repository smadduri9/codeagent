"""Every declared event name is emitted from somewhere in src."""

from pathlib import Path

import codeagent
from codeagent.observability.events import EVENT_NAMES


def test_every_declared_event_is_emitted() -> None:
    root = Path(codeagent.__file__).parent
    text = "\n".join(p.read_text() for p in root.rglob("*.py") if p.name != "events.py")
    missing = sorted(name for name in EVENT_NAMES if f'"{name}"' not in text)
    assert missing == []
