# Platform notes

Documented differences between macOS (primary, arm64) and Linux (CI). Tests that cannot behave identically on both platforms are skipped or adapted with the reason recorded here.

## macOS arm64

- Primary development target. Git worktrees and `start_new_session` process groups behave as on Linux.
- `/bin/bash` is the system bash used by the `bash` tool (`bash -lc`).

## Linux

- CI runs the same `scripts/check.sh` suite. Git worktree isolation is covered in unit tests.
- GNU coreutils: tests use `git` and `/bin/sh` rather than macOS-only flags.

## BSD and GNU command differences

- File tools invoke `rg` (ripgrep) from `PATH`; both platforms must have it installed in CI/dev.
- Tests avoid GNU-only `find` flags; the permission allowlist uses portable `find . -name` patterns.

## Process groups and signals

- On POSIX, `run_command` and `bash` start children with `start_new_session=True` so timeouts can `killpg` the whole group.
- On non-POSIX platforms, timeout handling falls back to `Popen.kill()` on the direct child only. The timeout integration test is POSIX-only (`test_uses_process_group_on_posix`).

## Paths and case sensitivity

- Workspace path rules use `Path.resolve()` / `realpath` semantics. macOS default APFS is case-insensitive; Linux ext4 is case-sensitive. Permission tests use explicit path casing.

## Docker

- Optional sandbox (`isolation.mode = "docker"`) is not implemented in Phase 4. See `DESIGN.md` 8.15.
