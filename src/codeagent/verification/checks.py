from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class VerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    status: Literal["pass", "fail", "skipped", "unavailable", "flaky"]
    command: list[str] | None
    duration_ms: int
    evidence: str
