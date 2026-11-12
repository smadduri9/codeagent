# 0017: The repeat guard restarts its window after a successful edit

## Context

`DESIGN.md` 8.12 defines the repeat detector as "identical tool and arguments
three times within six calls", warning once and stopping if it recurs. The
implementation matched that literally, so a normal fix loop (edit, run the same
test command, edit, run it again) warned on the third test run and stopped the
run with `repeat_tool_calls` on the fourth. The warning was also only stored on
`RunResult`; the model never saw it, although 8.12 says it is injected.

## Decision

1. A successful `write_file` or `edit_file` clears the detector's window
   (`LoopGuards.on_workspace_changed`). An identical call after the workspace
   changed is a new observation, not a repeat. Failed edits do not clear it.
2. When the warning first fires, the loop appends it to the history as a user
   message after that turn's tool results, so the model can change approach.

The thresholds (three within six, warn once, then stop) are unchanged. No
public signature changes; `LoopGuards` gains one method. Reference: fix round 1,
FIX-06.

## Consequences

- Tests: `tests/unit/test_repeat_guard.py` covers the edit-then-test loop, a
  loop of failing edits (still stopped), and the injected warning.
  `tests/unit/test_loop.py::test_repeat_guard_warns_then_stops` is unchanged.
- Edits made through `bash` or `run_command` are not recognised as workspace
  changes, so a loop that edits only through the shell can still be stopped.
- A model that alternates a trivial successful edit with the same failing call
  is no longer caught by this guard; iteration, token and tool-call budgets
  remain the backstop.
- The injected warning is not persisted, so a resumed run does not replay it.
