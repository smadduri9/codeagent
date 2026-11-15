# 0018: `codeagent run` is isolated by default; `chat` is not yet

## Context

`DESIGN.md` D6 and 8.14 make a dedicated git worktree the default, and 8.19
lists plain `codeagent run "<goal>"`. Persistence was added in Phase 5 behind a
`--persist` flag whose default stayed off, so a plain `run` edited the user's
checkout directly with no SQLite state, budgets, compaction or workflow tools.

Flipping the default was unsafe until a finished run kept its work (FIX-07),
tools looked at the worktree (FIX-08), and rollback and resume worked on a
finished run (FIX-09, FIX-10).

## Decision

1. `codeagent run` persists and isolates by default. The flag becomes
   `--persist/--no-persist`; `--no-persist` keeps the old direct-edit behaviour.
2. A worktree is created from the last commit. When the checkout has uncommitted
   changes the CLI says they are not part of the run.
3. `codeagent chat` is unchanged and still edits the checkout directly. It now
   prints one line saying so. A chat session spans several turns, and isolating
   it needs one worktree for the whole session plus defined resume and rollback
   semantics; that is a separate feature, not a default flip.

`execute_agent_run(persist=...)` keeps its `False` default so library callers
and evaluations are unaffected. Reference: fix round 1, FIX-11.

## Consequences

- Tests: `tests/unit/test_run_defaults.py`.
  `tests/unit/test_cli_run.py::test_run_with_fake_script` now passes
  `--no-persist` because it runs inside the project checkout; its assertions are
  unchanged.
- Every `run` now leaves a `codeagent/<run_id>` branch when it changed files.
  Nothing prunes old branches; the operator deletes them with `git branch -D`.
- Open: isolation for `chat` (owner decision), and branch housekeeping.
