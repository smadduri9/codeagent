# 0013: Test-only crash hook and the `slow` marker

## Context

Crash-resume tests need a real process that dies mid tool call. Killing from
outside is racy, so the loop gets a hook: `CODEAGENT_TEST_CRASH_AT=tool_started`
sends SIGKILL to the process just before a tool runs.

Those tests also start a subprocess, which is too slow for the default run
unless marked.

## Decision

- `_maybe_crash` in `src/codeagent/loop/runner.py` reads one environment
  variable. Without it the hook does nothing. Only the crash test sets it.
- A `slow` pytest marker is registered in `pyproject.toml`. It marks subprocess
  tests. The default check script still runs them, because they take under a
  second each.
- Resume rule: a run with no stop reason, still in the `WORKING` phase, is now
  resumable. A process that died mid-run never wrote a stop reason. Before this
  change such a run could not be resumed at all.

## Consequences

- Public behaviour changes in one case: a run that was killed can now be
  resumed. Runs that are still active in another process are not protected by
  this rule. The run lock, not `can_resume_run`, prevents concurrent resume, and
  that is unchanged.
- The hook is in shipped code. Its risk is limited to an environment variable a
  user would have to set on purpose.
