# 0006 — Tool-agnostic build operation

## Context

The build was documented as running through `scripts/autobuild.sh` (Cursor CLI)
or the Codex driver in `.autobuild/`, both of which require a vendor CLI
credential. The owner currently has an authenticated Cursor **UI** session but no
CLI credential, and a Codex run halted on usage limits. The owner asked that the
build be runnable from a UI and portable across tools (Cursor UI/CLI, Codex,
Claude Code) so that hitting one tool's limit never blocks progress.

The build logic is in fact already vendor-neutral: it is fully specified by
`DESIGN.md`, `BUILD_PLAN.md`, and `AGENTS.md`, and all state lives in git plus
`docs/PROGRESS.md`. Only the *driver harness* (the loop that feeds prompts to a
CLI and gates between sessions) was tool-specific. P1-F1 was completed through the
Cursor UI with no driver, confirming this.

A second, latent issue: `AGENTS.md` said "never ask a question," which is correct
unattended but wrong when the owner is present in a chat and a choice is genuinely
theirs.

## Decision

Make the tool-agnostic path explicit without changing what gets built or how it is
verified:

1. Add `docs/RUNBOOK.md`: an operator guide stating the build is tool-agnostic,
   listing the invariants that every tool/mode must honor, carrying the exact
   per-phase/review/fix prompts (copied verbatim from the drivers) plus a
   "do one feature" prompt for UI use, and a tool-switching table.
2. Clarify `AGENTS.md` "Operating mode" into **two modes** — unattended (never
   ask) and interactive/UI (may ask the owner when the choice is theirs) — and
   point to the runbook. No change to the merge policy, git rules, or
   "Never do these".
3. Note in `BUILD_PLAN.md` §6.5 that the prompts are the contract and the CLI
   driver is one optional way to run them; any agent against `git` and `gh` works.

The CLI drivers are retained unchanged as the unattended option. No public code
interface changes. Because `AGENTS.md` and `BUILD_PLAN.md` are owner-owned, these
edits were made at the owner's explicit request and are recorded here.

## Consequences

- The build can proceed from the Cursor UI with no CLI credential, and can hand
  off to Codex or Claude Code at any clean git point by re-syncing `main` and
  pasting the same prompt. Nothing is held outside git and `docs/PROGRESS.md`.
- Tools without the Cursor deny-list (`.cursor/cli.json`) — Codex, Claude Code —
  must self-enforce the invariants (no `rm`, never touch `.env`, never push to
  `main`). The runbook states this explicitly; it is a documentation guarantee,
  not an automated one.
- The interactive mode permits questions, which could reduce autonomy if overused;
  it is scoped to choices that are genuinely the owner's, and unattended runs are
  unaffected.
- Follow-up: none required. If a future tool needs its own thin driver, model it
  on the existing ones; the prompts in the runbook are the shared contract.
