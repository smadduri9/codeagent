# RUNBOOK: operating the build with any agent

This project is **tool-agnostic**. The authoritative plan lives in `DESIGN.md`,
`BUILD_PLAN.md`, and `AGENTS.md`; the state lives in git plus `docs/PROGRESS.md`.
Nothing about continuing the build requires a specific vendor. Any capable agent
— the **Cursor UI**, the **Cursor CLI**, **Codex**, or **Claude Code** — can run
it, because the work is just: read the docs, pick the next feature, use `git` and
`gh`, and run `scripts/check.sh`.

The CLI drivers (`scripts/autobuild.sh` for Cursor, `.autobuild/` for Codex) are
**one optional way** to run the prompts below unattended. They are not required.
If you have no CLI credentials, or a tool hits its usage limit, switch tools and
keep going from the same git state. See "Switching tools" below.

---

## Two operating modes

- **Unattended** — a driver runs with no human present. The agent never asks a
  question: it decides, records the decision in `docs/decisions/`, and continues
  (`AGENTS.md` → Operating modes). This is what `scripts/autobuild.sh` and the
  Codex driver do.
- **Interactive (UI)** — you (the owner) are present in a chat. The agent may ask
  you a question when a choice is genuinely yours, but otherwise behaves exactly
  as unattended: same branches, same checks, same safety rules. This is the mode
  you use when you paste a prompt below into Cursor, Codex, or Claude Code.

Both modes obey the same invariants (next section). Switching modes or tools is
always safe because no state is held outside git and `docs/PROGRESS.md`.

---

## Invariants every tool and mode must honor

These come from `AGENTS.md` and `BUILD_PLAN.md` §3. They do **not** depend on any
vendor's permission system, so an agent running under Codex or Claude Code must
self-enforce them (only the Cursor deny-list in `.cursor/cli.json` is automatic).

1. Start from an up-to-date `main`: `git fetch`, `git switch main`,
   `git pull --ff-only`, then `scripts/check.sh`.
2. One feature → one branch (`feat/<id>-<slug>`) → one pull request. Never
   implement a later feature early.
3. `scripts/check.sh` is green before **every** commit and before opening a PR.
4. Push after every green commit. Never push to `main`. Never force-push or
   rewrite pushed history.
5. Open a PR with `gh pr create`, wait for both CI checks
   (`check (ubuntu-latest)`, `check (macos-latest)`), then merge per the
   `AGENTS.md` merge policy (`auto` → merge your own PR after CI passes).
6. After merge: `git switch main`, `git pull --ff-only`, re-run `scripts/check.sh`,
   update `docs/PROGRESS.md` on a branch (never directly on `main`).
7. Never read, print, log, or commit secrets. `GROQ_API_KEY` lives only in the
   owner's local `.env`; do not open it. Never commit `.env`, `.autobuild/`,
   `.codeagent/`, or `*.db`.
8. Delete files with `git rm` or Python, never the shell `rm`.
9. Tests are never deleted or weakened to pass. No network, no sleeps > 1s, no
   real keys; use `FakeProvider`. Live tests are `@pytest.mark.live`, skipped by
   default.
10. If stuck after three distinct attempts: push the branch, open a **draft** PR
    labeled `blocked`, note it in `docs/PROGRESS.md`, and stop.

If a document conflict can't be settled, record a decision in `docs/decisions/`
and choose the smallest reasonable option.

---

## The prompts (identical across tools)

These are the exact prompts the drivers use. Paste the one you need into any
agent. `N` is the phase number (0–10); the feature list and order are in
`BUILD_PLAN.md` §5, and the next `todo` feature is the top of `docs/PROGRESS.md`.

### Continue / run a phase

> Read `AGENTS.md`, `DESIGN.md`, `BUILD_PLAN.md`, and `docs/PROGRESS.md`. Follow
> the session-start checklist in `BUILD_PLAN.md` §6.2. We are working on Phase N.
> Work feature by feature using the per-feature loop in §6.3 — commit, push, open
> pull requests, and merge as §3 specifies and `AGENTS.md` allows. When the last
> feature of the phase has merged, update `docs/PROGRESS.md`, create and push the
> tag `phase-N`, print the phase report, and stop. If a feature is stuck after
> three distinct attempts, follow §3.11 and stop.

### Do just the next one feature (handy in the UI)

> Read `AGENTS.md`, `BUILD_PLAN.md`, and `docs/PROGRESS.md`. Take the earliest
> feature whose status is `todo` (or continue the one marked `in-progress`).
> Implement only that feature on its own `feat/<id>-<slug>` branch following the
> per-feature loop in `BUILD_PLAN.md` §6.3: tests with code, `scripts/check.sh`
> green before every commit, push, open a PR with acceptance evidence, wait for
> CI, merge per the merge policy, then update `docs/PROGRESS.md` on a branch.
> Stop after this one feature merges.

### Read-only phase review

> Review the code merged in Phase N against `DESIGN.md`. Report (1) deviations
> from the design, (2) edge cases from `DESIGN.md` §10 not handled, (3) any place
> a tool call or permission rule could be bypassed, (4) any test that would pass
> even if the feature were broken, (5) any place the system prompt plus tool
> definitions or a request could exceed the free-tier limits of `DESIGN.md` 8.20.
> Mark each finding high, medium, or low. Do not change code. End with exactly one
> line: `VERDICT: PASS` or `VERDICT: FAIL`. Use FAIL if there is any high finding.

Save the answer to `.autobuild/reviews/phase-N.md` (git-ignored) if you want the
drivers to pick it up later.

### Fix round after a failed review

> Read `AGENTS.md` and the review in `.autobuild/reviews/phase-N.md`. For each
> finding marked high or medium, make a `fix/` branch, add a test that fails
> without the fix, fix it, and merge through a pull request per `BUILD_PLAN.md`
> §3. Record any finding you reject, with a reason, in `docs/decisions/`. Stop
> when done.

---

## Switching tools (Cursor ⇄ Codex ⇄ Claude Code)

Because all state is in git and `docs/PROGRESS.md`, a handoff is just:

1. The current tool finishes or stops at a clean point: either a merged PR, or a
   pushed branch with its PR open (draft + `blocked` label if it is stuck).
2. In the new tool, open the repo, run `git fetch && git switch main &&
   git pull --ff-only && scripts/check.sh`, then paste the relevant prompt above.

Nothing is lost between tools. The only differences to know:

| Tool | Credentials | Safety enforcement | Notes |
|---|---|---|---|
| **Cursor UI** | Your signed-in app session (no CLI key needed) | `.cursor/cli.json` deny-list applies; you approve actions interactively | What you are using now. Good default when you have no CLI key. |
| **Cursor CLI** (`scripts/autobuild.sh`) | `agent login` or `CURSOR_API_KEY` | `.cursor/cli.json` deny-list applies | Unattended driver; needs a CLI credential. |
| **Codex** (`.autobuild/`) | Codex account / credits | Driver preflight + the invariants above | Falls back here when Cursor is unavailable; watch usage limits. |
| **Claude Code** | Anthropic account | The invariants above (no Cursor deny-list) | Must self-enforce the invariants; same prompts work. |

Because Codex and Claude Code do **not** read `.cursor/cli.json`, the agent there
is responsible for the invariants directly — especially "no `rm`", "never touch
`.env`", and "never push to `main`".

---

## Quick status check

Run these any time to see where the build is, in any tool:

```bash
git fetch --prune
git switch main && git pull --ff-only
scripts/check.sh                      # must be green
grep -n '| P' docs/PROGRESS.md        # feature statuses
gh pr list --state open               # anything in flight
gh pr list --label blocked --state open   # anything stuck
git tag -l 'phase-*'                  # which phases are done
```

The next thing to build is the earliest row in `docs/PROGRESS.md` whose status is
not `merged`. Phase ends when its `phase-N` tag exists on `origin`.
