from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GateAction(StrEnum):
    COMPLETE = "complete"
    PROMPT_VERIFY = "prompt_verify"
    COMPLETE_UNVERIFIED = "complete_unverified"


@dataclass
class CompletionGate:
    edits_since_verify: bool = False
    verified_since_edit: bool = True
    prompted: bool = False

    def note_edit(self) -> None:
        self.edits_since_verify = True
        self.verified_since_edit = False

    def note_verification_pass(self) -> None:
        self.verified_since_edit = True
        self.edits_since_verify = False
        self.prompted = False

    def on_model_stop(self) -> GateAction:
        if not self.edits_since_verify or self.verified_since_edit:
            return GateAction.COMPLETE
        if not self.prompted:
            self.prompted = True
            return GateAction.PROMPT_VERIFY
        return GateAction.COMPLETE_UNVERIFIED

    @staticmethod
    def prompt_message() -> str:
        return "Run verification or explain why it does not apply before finishing."
