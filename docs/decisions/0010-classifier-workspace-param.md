# 0010: Shell classifier takes the workspace

## Context

`classify_segment` returned Allow for read-only commands such as `cat`, `head`
and `grep` without looking at their path arguments. `cat ~/.ssh/id_rsa` and
`cat ../../.env` were therefore allowed, which bypassed the path rules that
`path_read_decision` already applies to the file tools.

## Decision

`classify_segment` and `classify_argv` take a required keyword-only argument,
`workspace: Path`. For commands in `_PATH_ARG_COMMANDS` (`ls`, `cat`, `head`,
`tail`, `wc`, `grep`, `rg`, `find`), each path argument is checked with
`path_read_decision`, and the strictest result wins. A leading `~` is expanded
first. Pattern arguments of `grep` and `rg` are skipped, and numeric arguments
of `head` and `tail` are skipped.

Public interface change: the two classifier functions gain one keyword-only
argument. DESIGN 8.6 describes the classifier; its signatures differ by that
keyword. The only other caller, `permissions/engine.py`, is updated.

## Consequences

- Tests: `tests/unit/test_shell_classify.py::test_read_paths` covers denied,
  secret, allowed and pattern-argument cases. `test_unknown_segment_defaults_ask`
  now passes `workspace`.
- Limitation: paths in commands outside `_PATH_ARG_COMMANDS` are not checked
  here. Redirection targets are still checked by `extract_redirect_paths`.
- Follow-up: S3 adds flag rules to the same commands.
