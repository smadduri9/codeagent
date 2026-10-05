# 0008: Phase 9 repository intelligence skipped (gate not met)

## Status

Accepted (updated with live baseline metrics)

## Context

DESIGN 9.1 and BUILD_PLAN Phase 9 require a baseline report from P8-F9 before
building repository intelligence. The gate needs measured live failure data or a
completed live core12 slice.

## Decision

Skip Phase 9 features P9-F1 through P9-F9 until the live gate passes. The first
live baseline session recorded **0–N core12 tasks** (see `evals/baselines/gate-conclusion.md`);
search-heavy failure rate did not justify repository intelligence.

## Measured data

See `evals/baselines/gate-conclusion.md` and `evals/baselines/live-core12-partial.md`
for tasks completed, pass rate, search-call share on failures, and token totals.

## Consequences

- No `search_symbol`, `find_references`, or intelligence index until the gate passes.
- PROGRESS lists Phase 9 items as `skipped` with a link to this decision.
- Phase 10 explore helper is not merged (depends on eval evidence).
