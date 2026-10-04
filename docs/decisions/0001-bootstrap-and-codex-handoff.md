# Bootstrap and Codex build handoff

## Context

The owner requested implementation using Codex even though the build documents
describe Composer 2.5. The product design remains unchanged. The repository has
no phase labels or `blocked` label; AGENTS.md reserves their creation for the
owner. P0-F1 also precedes P0-F2, which introduces required CI checks.

## Decision

Implement and verify P0-F1 locally. Automatic approval review rejected the
initial push because it requires explicit owner permission to publish the new
code to GitHub. No push or PR was performed. Keep the verified feature branch
local until permission is granted; do not merge or claim the phase is complete.
Phase labels and `blocked` must also be created by the owner or explicitly
authorized. After both prerequisites, publish and resume P0-F1. Local checks are
the bootstrap evidence because CI does not exist until P0-F2; the next session
must explicitly record that bootstrap exception before merging.

Prepare an ignored, local Codex continuation driver under `.autobuild/` for
the owner to launch. Do not modify the owner-supplied Cursor driver or rules.
Use the installed CLI's automatic approval review with its workspace sandbox,
and halt if an action cannot be approved. Do not disable the sandbox or bypass
approvals. The owner runs label setup themselves before launching.

## Consequences

Ruff's file selection is explicitly limited to Python, notebooks, and its TOML
configuration. Ruff 0.16 also discovers Markdown code blocks by default; the
owner-supplied design contains illustrative pseudocode that must not be rewritten.

Only P0-F1 is implemented by this session. Later features retain their
prescribed ordering and PR boundaries. The local driver is a build convenience,
not a shipped CodeAgent feature, and is not present in fresh clones. All
remaining implementation and phase reviews run in subsequent bounded sessions.
