# 0011: Child processes receive an allowlisted environment

## Context

`filtered_environment` in `src/codeagent/tools/command_exec.py` removed only
variables whose names end in `_API_KEY`, `_SECRET`, `_TOKEN` or `_PASSWORD`. Any
other secret, such as a database URL with a password, reached child processes
the agent started.

## Decision

Child processes receive only keys in a fixed base allowlist (`PATH`, `HOME`,
`LANG`, `LC_*`, and similar), plus keys passed by the caller through the new
keyword `passthrough`. Secret-looking keys are always dropped, even when
passed through. Tool-set `extra` values still apply, minus secret-looking keys.

No configuration setting is added. Making `passthrough` configurable is
deferred.

Public interface change: `filtered_environment` gains one keyword-only
parameter, `passthrough`. Existing calls are unchanged.

## Consequences

- Tests: `tests/unit/test_command_exec.py` covers allowlist behavior and
  passthrough with secrets.
- Limitation: commands that need other variables, such as `GOPATH` or
  `NODE_PATH`, no longer see them until the allowlist or passthrough is extended.
- Follow-up: expose `passthrough` through settings if real use needs it.
