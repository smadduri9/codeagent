# 0009: Docker sandbox approach (supersedes deferral in 0007)

## Status

Accepted

## Context

DESIGN 8.15 requires optional `isolation.mode = "docker"` for command execution with
bind-mounted workspace, no network by default, and a loud fallback when Docker is
missing. Decision 0007 deferred implementation; production coding agents typically
combine **filesystem isolation** (git worktree or copy) with **optional process
isolation** for shell commands:

- **Cursor / Claude Code (typical):** edits stay in a workspace boundary; shell
  commands run on the host with policy gates, or in a remote/cloud sandbox when
  enabled—not every file read goes through a container.
- **This product:** worktree/branch isolation remains the default for git state;
  Docker applies only to `run_command` and `bash`, matching DESIGN 8.15.

## Decision

Implement Docker command execution behind `isolation.mode = "docker"`. Git isolation
continues to use worktree with branch fallback (Docker does not replace worktrees).
Use image `python:3.12-bookworm-slim`, `--network none`, bind-mount the workspace
read-write at the same absolute path, `-w` set to that path. If `docker` is missing,
not running, or the run fails before start, emit a **stderr warning** and execute on
the host via the existing `run_argv` path (never fail silently). CI skips live
Docker tests when the daemon is unavailable.

## Consequences

- P8-F10 is delivered; PROGRESS marks P8-F10 merged.
- 0007 remains historical; this record is authoritative for sandbox behavior.
- macOS arm64 uses the same slim image tag; owners may override the image in a
  future config key without changing the default enum shape.
