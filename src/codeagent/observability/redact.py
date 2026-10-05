import re

_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+\S+", re.I),
)


def redact_secrets(text: str) -> str:
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def redact_payload(payload: dict[str, object] | None) -> dict[str, object] | None:
    if payload is None:
        return None
    return {k: redact_secrets(v) if isinstance(v, str) else v for k, v in payload.items()}
