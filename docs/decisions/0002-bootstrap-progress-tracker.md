# Bootstrap progress tracking

## Context

P0-F3 introduces the full progress tracker, but the per-feature workflow requires
recording P0-F2's state before implementation.

## Decision

Create a minimal Phase 0 tracker on P0-F2's branch. P0-F3 still owns the complete
feature table, template, platform notes, and coverage test. No later product
feature is implemented early.

## Consequences

Interrupted sessions can resume P0-F2 using a durable progress row.
