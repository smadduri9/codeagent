# 0008: Phase 9 repository intelligence skipped (gate not met)

## Status

Accepted

## Context

DESIGN 9.1 and BUILD_PLAN Phase 9 require a baseline report from P8-F9 before
building repository intelligence. The gate needs measured live failure data or a
completed live core12 slice.

## Decision

Skip Phase 9 features P9-F1 through P9-F9 in this build. P8-F9 recorded
**undetermined — repository intelligence stays off** because no live core12 tasks
ran in the build session.

## Consequences

- No `search_symbol`, `find_references`, or intelligence index in this release.
- PROGRESS lists Phase 9 items as `skipped` with a link to this decision.
- Phase 10 explore helper is not merged (depends on eval evidence).
