# Record the phase boundary through the final feature branch

## Context

BUILD_PLAN 3.8 requires the completed tracker to include the last feature's
merge commit, while AGENTS.md requires progress changes through feature branches
and forbids direct main commits. A commit cannot contain its own future hash.

## Decision

Finalize the tracker in P0-F4's PR after the implementation passes CI, describing
its resulting state on merged main. While that PR remains open, its GitHub status
is authoritative and the phase remains incomplete. Use `phase-0^{commit}` as the
last feature's merge-commit reference instead of embedding its future hash.
Re-run both CI checks for the final documentation commit before merging. Only
after the PR is merged and main passes local checks, create and push the annotated
phase-0 tag on that merge commit. Confirm its resolved hash matches the PR.

## Consequences

Every feature still has one branch and one PR. Completion metadata ships through
the final feature branch, no extra metadata PR or direct main commit is needed,
and the phase tag never labels incomplete work. The final session report records
the resolved merge hash and successful tag publication.
