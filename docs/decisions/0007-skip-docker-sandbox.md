# 0007: Skip optional Docker sandbox (P8-F10)

## Status

Accepted

## Context

BUILD_PLAN P8-F10 delivers `isolation.mode = "docker"` with container execution,
macOS notes, and a not-running fallback. The initial release already ships
worktree and branch isolation from Phase 4.

## Decision

Defer Docker sandbox implementation. Configuration retains the `docker` enum value
for forward compatibility, but no container runner is wired in this release.

## Consequences

- CI and local runs continue to use worktree isolation.
- A future feature may implement P8-F10 without changing the public config shape.
- PROGRESS records P8-F10 as `skipped` with this decision.
