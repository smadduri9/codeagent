# CodeAgent: Build Plan

How CodeAgent is built with Cursor Composer 2.5 in agent mode, and how every feature reaches GitHub. `DESIGN.md` says what to build. This document says in what order, on which branches, with which commits, and how each piece is verified and merged. `AGENTS.md` carries the short standing rules the implementing agent reads every session.

Everything here is written for two readers: the owner (Sriram) who sets things up once and may inspect the result at any time, and the implementing agent that works feature by feature. The build is designed to run unattended: `scripts/autobuild.sh` starts one Cursor session per phase and checks the result between sessions. The model provider for the product, its tests, and its evaluations is Groq's free tier (DESIGN 8.20). The repository is https://github.com/smadduri9/codeagent (public).

---

## 1. Principles of the build

1. **Feature-wise history.** Every feature is developed on its own branch, pushed to GitHub, merged through a pull request, and recorded in `docs/PROGRESS.md`. `main` always passes CI.
2. **Small, green commits.** Each commit is one logical change and passes `scripts/check.sh`.
3. **Pushed early.** Work is pushed after every green commit, so a dead session loses nothing.
4. **Evidence over claims.** A feature is complete only when its acceptance checks have run and the evidence is in the pull request.
5. **One phase per session.** The agent works through the features of a single phase, tags it, and ends the session. The driver script starts a fresh session for the next phase, so no session needs a long memory.
6. **Never rewrite shared history.** No force-push, no history rewriting, no direct pushes to `main`.
7. **No waiting on a human.** The agent does not ask questions during an unattended build. A decision the documents leave open is recorded in `docs/decisions/`. A problem it cannot solve ends in a draft pull request labeled `blocked`, and the driver halts.

---

## 2. One-time setup by the owner

The implementing agent never handles credentials, repository settings, or the files that control its own permissions. The owner does these steps once. Files marked "owner-supplied" are delivered with this plan and committed by the owner, never by the agent.

1. The repository exists: https://github.com/smadduri9/codeagent (public, empty).
2. Authenticate the GitHub CLI on the development machine: `gh auth login`. The agent then uses `gh` and `git` with that login and never sees a token.
3. Install the Cursor CLI (`curl https://cursor.com/install -fsS | bash`) and sign in once with `agent login`, or export `CURSOR_API_KEY` in the shell that runs the driver. Confirm the model is available: `agent --list-models` shows the Composer 2.5 id. If its id differs from `composer-2.5`, set `CURSOR_MODEL` when running the driver.
4. Get a Groq API key at https://console.groq.com (free tier). Put it only in a local `.env` file in the repository folder: `GROQ_API_KEY=...`. Never paste it into a chat, a pull request, or a commit. The `.env` file is git-ignored and hidden from Cursor by `.cursorignore` and `.cursor/cli.json`.
5. Create the local repository, add the documents and the owner-supplied files, and make the initial commit on `main`:
   ```
   git clone git@github.com:smadduri9/codeagent.git && cd codeagent
   # copy in: DESIGN.md BUILD_PLAN.md AGENTS.md .gitignore .cursorignore .env.example
   #          .cursor/cli.json scripts/autobuild.sh
   chmod +x scripts/autobuild.sh
   git add DESIGN.md BUILD_PLAN.md AGENTS.md .gitignore .cursorignore .env.example .cursor/cli.json scripts/autobuild.sh
   git commit -m "docs: add design, build plan, agent rules, and build driver"
   git push -u origin main
   cp .env.example .env   # then edit .env locally and add the key
   ```
   If the clone uses HTTPS instead of SSH, that is fine as long as `gh auth setup-git` has been run.
6. Labels: `scripts/autobuild.sh` creates `phase-0` to `phase-10` and `blocked` itself at start-up, using your `gh` login. Nothing to do.
7. In the repository settings: allow merge commits (this keeps each feature's commits visible), and enable "automatically delete head branches". Branch protection for `main`, to be added after P0-F2 merges, because the CI check names do not exist before then: require the checks `check (ubuntu-latest)` and `check (macos-latest)` and block force-pushes. Until then, `main` is protected only by the agent's rules and the Cursor deny list, so the first phase is the riskiest window. Checking the exact names after the first CI run: `gh run view` or the pull request's checks tab.
   GitHub-hosted runners are free for public repositories, so running CI on both operating systems costs nothing here.
8. Choose the merge policy in `AGENTS.md` under "Merge policy": `auto` or `manual`. Fully unattended operation requires `auto`.
9. Keep the Mac awake, plugged in, and online while the driver runs (`caffeinate` is started by the driver; closing the lid on a laptop still sleeps it unless it is on power with an external display). Start it with `scripts/autobuild.sh`.

---

## 3. Git and GitHub workflow

### 3.1 Branches

| Pattern | Use |
|---|---|
| `main` | Always green. Changed only by merged pull requests, apart from the owner's own commits (the initial commit and later updates to the owner-supplied files). |
| `feat/<id>-<slug>` | A feature, for example `feat/p2-f3-grep-glob-tools`. |
| `fix/<id>-<slug>` | A bug found after a feature merged. |
| `test/<id>-<slug>` | Test-only or fixture-only work. |
| `docs/<id>-<slug>` | Documentation. |
| `chore/<id>-<slug>` | Tooling, CI, configuration. |
| `exp/<id>-<slug>` | Experiments, including ones that are rejected. Merged only with a decision record. |

`<id>` is the feature ID from section 5 (lowercase, for example `p3-f2`). One feature means one branch means one pull request.

### 3.2 Commit messages

Conventional Commits: `type(scope): subject`.

- Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`, `perf`.
- Scope: the module, such as `tools`, `permissions`, `state`, `loop`, `providers`, `verification`, `cli`.
- Subject: imperative mood, no trailing period, at most 72 characters.
- Body (when useful): what and why, wrapped at 80 columns. Reference the feature ID on the last line: `Feature: P3-F2`.
- Never include secrets, API keys, or personal data in a commit message or file.

### 3.3 Commit granularity

- One logical change per commit. Keep refactors separate from behavior changes.
- Aim for under about 400 changed lines per commit. Split larger changes.
- **Every commit passes `scripts/check.sh`.** To write tests first, mark them `@pytest.mark.xfail(strict=True, reason="P3-F2")` and remove the marker in the commit that makes them pass.
- Documentation that describes a feature ships in the same pull request as the feature.
- Commits that change `docs/PROGRESS.md` use `docs(progress): ...`.

### 3.4 Pushing

- Push the branch after every green commit: `git push -u origin <branch>` the first time, then `git push`.
- Allowed push targets: branches matching `feat/*`, `fix/*`, `test/*`, `docs/*`, `chore/*`, `exp/*`, and annotated tags matching `phase-*`.
- **Never:** `git push --force` or `--force-with-lease`, pushing to `main`, deleting remote branches by hand, or rewriting a pushed commit. If a branch needs updating from `main`, merge `main` into the branch.

### 3.5 Pull requests

Opened with `gh pr create` once the feature's acceptance checks pass locally. Use the template at `.github/pull_request_template.md`:

```markdown
## Feature
<ID and title, for example P3-F2 Shell classifier>

## What changed
<2 to 5 sentences>

## Acceptance evidence
- [ ] <criterion from BUILD_PLAN.md>: <test name or command output>
- [ ] `scripts/check.sh` passes locally (paste the final summary lines)

## Deviations from the design
<none, or what and why; link to docs/decisions/NNNN-*.md>

## Risks and follow-ups
<none, or list>
```

- Title is a conventional commit subject, for example `feat(permissions): classify shell commands`.
- Label with `phase-N` (the labels exist from setup step 6; if one is missing, the agent stops and reports rather than creating labels or changing settings).
- A pull request covers exactly one feature. If the work grew, split it.

### 3.6 Continuous integration

`.github/workflows/ci.yml` runs on every pull request and on pushes to `main`. A matrix job named `check` runs on `ubuntu-latest` and `macos-latest` (arm64). GitHub reports the two runs as `check (ubuntu-latest)` and `check (macos-latest)`; those are the names to require in branch protection.

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
jobs:
  check:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install ripgrep
        run: |
          if [ "$RUNNER_OS" = "macOS" ]; then brew install ripgrep; else sudo apt-get update && sudo apt-get install -y ripgrep; fi
      - name: Install project
        run: python -m pip install -e ".[dev]"
      - name: Check
        run: scripts/check.sh
      - name: Secret scan
        run: scripts/scan_secrets.sh
```

`scripts/check.sh` runs `ruff check .`, `ruff format --check .`, `mypy src`, and `pytest -q -m "not live"`. Live-provider tests are marked `live` and skipped in CI.

### 3.7 Merging

When CI is green and every acceptance box is checked:

- **Policy `auto`:** the agent merges with `gh pr merge --merge --delete-branch`. The merge commit preserves the feature's individual commits in the history.
- **Policy `manual`:** the agent stops after opening the pull request, records the pull request link in `docs/PROGRESS.md`, and reports. This stops the unattended build until the owner merges; it is for supervised use.

After a merge: `git switch main`, `git pull --ff-only`, confirm `scripts/check.sh` passes on `main`, then start the next feature.

### 3.8 Phase completion

When the last feature of a phase has merged:

1. Update `docs/PROGRESS.md`: mark the phase complete, with each feature's pull request link and merge commit.
2. Create an annotated tag `phase-N` on the merge commit of the last feature: `git tag -a phase-N -m "Phase N: <title>"`, then `git push origin phase-N`.
3. Write a short phase report in the final message: features merged, acceptance evidence, deviations, risks, and what the next phase assumes.
4. **End the session.** The driver then runs the read-only phase review (6.6) and starts the next phase.

### 3.9 Progress file

`docs/PROGRESS.md` is the shared memory between sessions. Each feature has one row:

```
| ID | Title | Branch | Status | PR | Merge commit |
```

Statuses: `todo`, `in-progress`, `in-review`, `merged`, `blocked`. The agent updates the row at the start of a feature (`in-progress`), when the PR opens (`in-review`), and after merge (`merged`). The agent reads this file at the start of every session to find the earliest unfinished feature.

### 3.10 Decisions

When the agent makes a choice the design leaves open, or must deviate from it, it writes `docs/decisions/NNNN-<slug>.md` (context, decision, consequences) in the same pull request. The goal of the design is preserved and the mechanism changed minimally.

### 3.11 When things go wrong

| Situation | Action |
|---|---|
| Local check fails | Fix on the same branch with a new commit. Do not weaken or delete a test to pass. |
| CI fails but local passes | Read the CI log with `gh run view --log-failed`, reproduce the platform difference, fix, note it in `docs/platform-notes.md`. |
| Merge conflict with `main` | `git merge main` into the feature branch, resolve, rerun checks. Never rebase a pushed branch. |
| Stuck after 3 distinct attempts | Push the branch, open a **draft** pull request labeled `blocked`, set the row to `blocked`, write what was tried and what is unknown, and end the session. The driver sees the label and halts. |
| A merged feature has a bug | New `fix/` branch and pull request. Never edit `main` history. |
| A secret is committed | Stop. The driver also checks for this and halts. The owner rotates the credential and decides about history cleanup. The agent does not rewrite history. |
| Groq daily quota exhausted during a live test | Do not retry. Skip the live test with a recorded note in the pull request, keep the scripted tests as the acceptance evidence, and continue. Live checks are rerun in a later session. |
| Cursor usage limit or CLI error | The session exits non-zero. The driver waits and retries, and halts after repeated failures. |
| Session dies mid-feature | Because the work was pushed, the next session reads `docs/PROGRESS.md`, checks out the branch, and continues. |

### 3.12 Allowed and forbidden git and `gh` commands

| Allowed without asking | Ask first | Forbidden |
|---|---|---|
| `git status/diff/log/show/branch/switch/checkout -b/add/commit/merge main/tag -a/fetch/pull --ff-only`, `git push` to allowed targets, `gh pr create/view/checks/merge`, `gh run view/list` | `git reset` of any kind, `git stash drop`, deleting local branches, `gh repo` and `gh auth` commands, changing repository settings | `git push --force` or `--force-with-lease`, pushing to `main`, `git rebase` on a pushed branch, `git filter-branch`, `git reset --hard origin/*` on a shared branch, `gh auth token`, writing credentials anywhere |

---

## 4. Files created in phase 0

Owner-supplied files are already on `main` and are not part of the agent's work: `.gitignore`, `.cursorignore`, `.env.example`, `.cursor/cli.json`, `scripts/autobuild.sh`. The agent extends `.gitignore` but never edits the other four.

These files are created by the agent and specified here so it builds them exactly.

**`scripts/check.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ruff check .
ruff format --check .
mypy src
pytest -q -m "not live"
```

**`scripts/scan_secrets.sh`:** fails if tracked files match patterns for provider API keys (including the `gsk_` prefix Groq keys use), private key headers, or `.env` contents. Also fails if `.env`, `.codeagent/`, `.autobuild/`, or `*.db` files are tracked.

**`.gitignore` (extended):** at minimum `.env`, `.env.*` (but not `.env.example`), `.codeagent/`, `.autobuild/`, `__pycache__/`, `.venv/`, `*.db`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`.

**`.github/pull_request_template.md`:** the template in 3.5.

**`.github/workflows/ci.yml`:** the workflow in 3.6.

**`docs/PROGRESS.md`:** a table with every feature from section 5, all `todo`.

**`docs/decisions/0000-template.md`:** context, decision, consequences.

---

## 5. Feature plan

Each feature lists: its **branch**, what it **delivers**, the **acceptance** checks that must pass, and the **commits** it should produce (in order). Commit lists are the expected shape, not a rigid script. Split further if a commit grows too large.

Format of IDs: `P<phase>-F<number>`.

### Phase 0: Bootstrap

**P0-F1 Project skeleton and tooling**
- Branch: `chore/p0-f1-project-skeleton`
- Delivers: `pyproject.toml` (Python 3.12, dev extras, ruff, mypy strict, pytest with a `live` marker), `src/codeagent/` package with `__init__.py` and a `--help` CLI, `scripts/check.sh`, `.gitignore`, minimal `README.md`.
- Acceptance: `scripts/check.sh` passes on the empty package; `codeagent --help` prints.
- Commits: `chore: add pyproject and tooling config` · `chore: add package skeleton and cli entrypoint` · `chore: add check script and gitignore` · `docs: add minimal readme`

**P0-F2 CI, pull request template, secret scan**
- Branch: `chore/p0-f2-ci-and-templates`
- Delivers: `.github/workflows/ci.yml`, `.github/pull_request_template.md`, `scripts/scan_secrets.sh`, a test proving the scan catches a planted fake key.
- Acceptance: CI runs green on this pull request on both operating systems; the scan fails on a planted fake key in a test fixture.
- Commits: `ci: add check workflow for ubuntu and macos` · `chore: add pull request template` · `ci: add secret scan script and test`
- After merge: the owner adds the `check` required-check rule (section 2, step 4).

**P0-F3 Progress file and decision records**
- Branch: `docs/p0-f3-progress-and-decisions`
- Delivers: `docs/PROGRESS.md` (all features, all `todo`, phase 0 features marked), `docs/decisions/0000-template.md`, `docs/platform-notes.md` (empty headings).
- Acceptance: a test parses `PROGRESS.md` and confirms every feature ID in this plan appears exactly once.
- Commits: `docs: add progress tracker` · `docs: add decision record template and platform notes` · `test(docs): verify progress file lists every planned feature`

**P0-F4 Layered configuration**
- Branch: `feat/p0-f4-config-loader`
- Delivers: Pydantic settings per DESIGN 8.18 (including `base_url`, `api_key_env`, `[request]`, `[tools]`, `[rate_limits]`); layering (defaults, user file, repository file, flags); optional price table; validation that rejects unknown keys; the `.env` loader described in DESIGN 8.18 (process environment first, then the git-root `.env`, then `~/.codeagent/.env`). Adds `python-dotenv` only if the standard-library parser is not enough; list the choice in the pull request.
- Acceptance: tests for each layer precedence, invalid values, missing files, and that no model name or price exists as a default in code; `.env` loader tests with temporary files showing precedence, that a value is never printed or logged, and that missing key gives a clear error naming the variable (not its value).
- Commits: `feat(config): add settings models and defaults` · `feat(config): add layered loading` · `feat(config): load api key from environment and .env` · `test(config): cover precedence, validation, and env loading`

Phase 0 ends: tag `phase-0`.

### Phase 1: Core types, provider protocol, loop skeleton

**P1-F1 Message, tool-call, and usage types**
- Branch: `feat/p1-f1-core-types`
- Delivers: `Message`, `ToolCall`, `ToolSpec`, `ToolResult`, `Usage`, `ModelEvent` types in `providers/base.py` and `tools/base.py`.
- Acceptance: round-trip serialization tests; strict typing passes.
- Commits: `feat(providers): add message and event types` · `feat(tools): add tool result and spec types` · `test: cover type serialization`

**P1-F2 Provider protocol and FakeProvider**
- Branch: `feat/p1-f2-fake-provider`
- Delivers: `Provider` protocol, scripted `FakeProvider` that replays turns including tool calls and usage.
- Acceptance: a test replays a three-turn script and receives the exact events.
- Commits: `feat(providers): add provider protocol` · `feat(providers): add scripted fake provider` · `test(providers): replay scripted turns`

**P1-F3 Tool registry**
- Branch: `feat/p1-f3-tool-registry`
- Delivers: registration, lookup, argument validation with Pydantic, unknown-tool errors, a truncation helper with the explicit marker, an `echo` test tool.
- Acceptance: malformed arguments produce a tool error and never call the tool; truncation keeps head or tail as configured.
- Commits: `feat(tools): add registry and validation` · `feat(tools): add truncation helper` · `test(tools): cover validation and truncation`

**P1-F4 Run lifecycle**
- Branch: `feat/p1-f4-run-lifecycle`
- Delivers: `RunPhase` enum and transition table (DESIGN 7), invalid transitions raise.
- Acceptance: every allowed transition passes; every disallowed one raises; each emits a log record.
- Commits: `feat(lifecycle): add run phases and transitions` · `test(lifecycle): cover all transitions`

**P1-F5 Agent loop with iteration guard**
- Branch: `feat/p1-f5-agent-loop`
- Delivers: `loop.py` per DESIGN 8.2 using native tool calls, the `max_iterations` guard, `stop_reason` recording (in memory for now).
- Acceptance: scripted run completes after one tool call; the loop stops exactly at `max_iterations`; a text-only reply ends the run.
- Commits: `feat(loop): add tool-call loop` · `feat(loop): add iteration guard` · `test(loop): cover completion and guard`

**P1-F6 Repeat and denial-streak guards**
- Branch: `feat/p1-f6-loop-guards`
- Delivers: repeat detector (three identical calls in six), one warning then stop; denial streak of three.
- Acceptance: scripted repeating model triggers the warning then the stop; denial streak stops the run.
- Commits: `feat(loop): add repeat detector` · `feat(loop): add denial streak guard` · `test(loop): cover repeat and denial guards`

**P1-F7 CLI run command with streaming output**
- Branch: `feat/p1-f7-cli-run`
- Delivers: `codeagent run` wired to the loop, streamed rendering of text and tool calls, a hidden `--fake-script` flag for demos and tests.
- Acceptance: an integration test runs the CLI with a fake script and checks the rendered output and exit code.
- Commits: `feat(cli): add run command` · `feat(cli): stream model and tool output` · `test(cli): run scripted session`

Phase 1 ends: tag `phase-1`.

### Phase 2: Filesystem and search tools

**P2-F1 Workspace boundary helper**
- Branch: `feat/p2-f1-workspace-paths`
- Delivers: one function that resolves a path against the workspace root with `realpath`, rejects escapes and escaping symlinks.
- Acceptance: tests for `../`, absolute paths, symlink out, symlink within, and nonexistent paths.
- Commits: `feat(tools): add workspace path resolution` · `test(tools): cover traversal and symlink cases`

**P2-F2 read_file and list_dir**
- Branch: `feat/p2-f2-read-and-list`
- Delivers: line-numbered `read_file` with offset and limit, binary and size rejection, `list_dir` respecting `.gitignore`.
- Acceptance: tests for ranges, binary rejection, size cap, ignore rules, truncation marker.
- Commits: `feat(tools): add read_file` · `feat(tools): add list_dir with gitignore support` · `test(tools): cover read and list behavior`

**P2-F3 glob and grep**
- Branch: `feat/p2-f3-glob-grep`
- Delivers: `glob` and `grep` (ripgrep wrapper with modes), results capped, `.gitignore` respected, clear error if `rg` is missing.
- Acceptance: tests on a fixture repository for each mode, caps, and the missing-binary error.
- Commits: `feat(tools): add glob` · `feat(tools): add grep wrapper` · `test(tools): cover search modes and caps`

**P2-F4 write_file and edit_file**
- Branch: `feat/p2-f4-write-and-edit`
- Delivers: `write_file` (new files only), `edit_file` (exact string, uniqueness, `replace_all`, read-before-edit, hash check, post-edit parse check where available, diff recording).
- Acceptance: tests for missing and ambiguous matches with line numbers, stale-read failure, unread-file failure, parse failure reporting, and existing-file refusal in `write_file`.
- Commits: `feat(tools): add write_file for new files` · `feat(tools): add edit_file with uniqueness checks` · `feat(tools): add read tracking and stale-file detection` · `test(tools): cover edit edge cases`

**P2-F5 move_path and delete_path**
- Branch: `feat/p2-f5-move-and-delete`
- Delivers: both tools with workspace checks and risk-level metadata (`delete_path` is always Ask once permissions exist).
- Acceptance: tests for inside and outside destinations, recursive delete flag, metadata present.
- Commits: `feat(tools): add move_path` · `feat(tools): add delete_path` · `test(tools): cover move and delete`

Phase 2 ends: tag `phase-2`.

### Phase 3: Permissions and untrusted content

**P3-F1 Risk levels, path and secret rules**
- Branch: `feat/p3-f1-risk-and-path-rules`
- Delivers: `RiskLevel`, `decide()` for file tools, path rules, secret-file rules, `edit_mode`.
- Acceptance: table-driven tests for each file tool across allow, ask, deny.
- Commits: `feat(permissions): add risk levels and decision types` · `feat(permissions): add path and secret rules` · `test(permissions): table test file tool decisions`

**P3-F2 Shell parser and classifier**
- Branch: `feat/p3-f2-shell-classifier`
- Delivers: `shell_parse.py` and rules per DESIGN 8.6 (split, per-segment class, substitution and heredoc handling, redirect-as-write).
- Acceptance: a table test with at least 80 cases covering allow, ask, deny, compound commands, substitution, redirects, `find -delete`, `git push --force`, and unknown commands. **Unknown must return Ask.** Before implementing, the agent re-reads the table against DESIGN 8.6, section 10, and the 12 security tests of section 11.1, adds missing rows, and lists the added rows in the pull request.
- Commits: `test(permissions): add shell classification cases` · `feat(permissions): add shell parser` · `feat(permissions): add segment classifier and rules` · `test(permissions): cover compound and edge commands`

**P3-F3 Policy gate in the loop**
- Branch: `feat/p3-f3-policy-gate`
- Delivers: validate then decide then record then execute; no tool runs before its decision is recorded; non-interactive mode turns Ask into Deny.
- Acceptance: a test fails if any tool executes without a prior decision record; non-interactive denial test.
- Commits: `feat(loop): enforce policy decision before execution` · `feat(permissions): add non-interactive mode` · `test(loop): prove no execution without a decision`

**P3-F4 Approval UI and single-use approvals**
- Branch: `feat/p3-f4-approvals`
- Delivers: CLI prompt (approve once, deny with message, allow for session), approval records bound to an argument hash, single use.
- Acceptance: replaying an approval fails; a changed argument fails; deny messages reach the model; session allowance is not persisted.
- Commits: `feat(permissions): add approval records` · `feat(cli): add approval prompt` · `test(permissions): cover single-use and binding`

**P3-F5 Untrusted output wrapping**
- Branch: `feat/p3-f5-untrusted-content`
- Delivers: delimiter wrapping of all tool results, system prompt wording placeholder, proof the engine never reads model-visible text.
- Acceptance: injection fixture tests (file containing an instruction, command output containing an instruction) show no change to decisions.
- Commits: `feat(permissions): wrap tool results as untrusted` · `test(security): injected instructions do not alter decisions`

**P3-F6 Security suite**
- Branch: `test/p3-f6-security-suite`
- Delivers: `tests/security/` with all twelve checks listed in DESIGN 11.1 that are testable at this point (the rest are added by the phase that introduces the behavior and tracked in `PROGRESS.md`).
- Acceptance: suite passes in CI on both operating systems.
- Commits: `test(security): add path, deletion, and approval tests` · `test(security): add secret path and injection tests`

Phase 3 ends: tag `phase-3`. The driver's phase review (6.6) gates phase 4.

### Phase 4: Command execution, git isolation, checkpoints

**P4-F1 run_command (argument array)**
- Branch: `feat/p4-f1-run-command`
- Delivers: no-shell execution, timeout with process-group kill, combined output with tail-preserving cap, filtered environment (no provider keys).
- Acceptance: tests for timeout killing a `sleep`, tail preservation, environment filtering, nonzero exit reporting.
- Commits: `feat(tools): add run_command` · `feat(tools): add timeout and output caps` · `test(tools): cover timeout and environment filtering`

**P4-F2 bash (shell string)**
- Branch: `feat/p4-f2-bash-tool`
- Delivers: `bash` tool wired to the classifier; same execution guarantees as `run_command`.
- Acceptance: classified Allow runs; Ask requires approval; Deny never runs; redirects obey path rules.
- Commits: `feat(tools): add bash tool` · `test(tools): cover classification outcomes through bash`

**P4-F3 Git wrapper and read-only git tools**
- Branch: `feat/p4-f3-git-tools`
- Delivers: typed git wrapper, `git_status`, `git_diff`, `git_log`, `git_show`.
- Acceptance: tests with temporary repositories, including a repository with no commits and one with a dirty tree.
- Commits: `feat(isolation): add git wrapper` · `feat(tools): add read-only git tools` · `test(tools): cover git tools in temp repos`

**P4-F4 Worktree isolation with branch fallback**
- Branch: `feat/p4-f4-worktree-isolation`
- Delivers: worktree manager per DESIGN 8.14, branch mode with dirty-tree prompt, baseline recording, the run lock file.
- Acceptance: user's working tree is unchanged after a run; branch mode never discards pre-existing changes; a second run is refused by the lock.
- Commits: `feat(isolation): add worktree manager` · `feat(isolation): add branch fallback and baseline` · `feat(isolation): add run lock` · `test(isolation): cover worktree and dirty-tree cases`

**P4-F5 Checkpoints, rollback, final diff**
- Branch: `feat/p4-f5-checkpoints-rollback`
- Delivers: checkpoint commits, `codeagent rollback`, diff stat and final diff output.
- Acceptance: rollback restores files to a chosen checkpoint; no automatic push occurs anywhere.
- Commits: `feat(isolation): add checkpoint commits` · `feat(cli): add rollback command` · `feat(cli): print final diff` · `test(isolation): cover rollback and no-push`

**P4-F6 Platform notes and cross-OS tests**
- Branch: `docs/p4-f6-platform-notes`
- Delivers: `docs/platform-notes.md` filled with macOS and Linux differences found (BSD vs GNU flags, process groups, path case); tests skip or adapt with a documented reason.
- Acceptance: CI green on both operating systems.
- Commits: `docs: record macos and linux differences` · `test: adapt platform-sensitive tests`

Phase 4 ends: tag `phase-4`.

### Phase 5: State, resume, budgets

**P5-F1 SQLite store and migrations**
- Branch: `feat/p5-f1-sqlite-store`
- Delivers: schema per DESIGN 8.8, migration runner, WAL mode, typed access layer.
- Acceptance: create, load, update tests; a migration applies cleanly on an empty database and on an existing one.
- Commits: `feat(state): add schema and migrations` · `feat(state): add store access layer` · `test(state): cover create, load, update, migrate`

**P5-F2 Persist the run**
- Branch: `feat/p5-f2-persist-run`
- Delivers: the loop records runs, steps, tool calls, decisions, approvals, plan items, `files_read`; phase transitions persisted.
- Acceptance: after a scripted run, every table holds the expected rows; a decision row exists before every tool row.
- Commits: `feat(state): persist steps and tool calls` · `feat(state): persist approvals and file reads` · `test(state): verify rows after a scripted run`

**P5-F3 Resume**
- Branch: `feat/p5-f3-resume`
- Delivers: `codeagent resume`, history rebuilt from the store, working-tree reconciliation, stale-read invalidation, `codeagent status`.
- Acceptance: kill a scripted run mid-way, resume, reach the same final state as an uninterrupted run; external file change triggers a warning and forced re-read.
- Commits: `feat(state): rebuild history from store` · `feat(cli): add resume and status` · `feat(state): reconcile working tree on resume` · `test: kill and resume a scripted run`

**P5-F4 Budgets and graceful exhaustion**
- Branch: `feat/p5-f4-budgets`
- Delivers: token, cost, tool-call, and wall-clock guards; exhaustion procedure (stop mutating, persist, report accomplished work, current failure, changed files, verification state, suggested continuation).
- Acceptance: each guard stops a scripted run at its limit with the correct `stop_reason`; the exhaustion report contains all required fields.
- Commits: `feat(loop): add token and cost guards` · `feat(loop): add tool-call and runtime guards` · `feat(loop): add exhaustion report` · `test(loop): cover each budget`

**P5-F5 Interrupt handling**
- Branch: `feat/p5-f5-interrupts`
- Delivers: first Ctrl-C finishes the current tool and stops cleanly; second stops immediately; state consistent either way.
- Acceptance: tests that deliver SIGINT mid-tool and mid-model-call and then verify the database is consistent and resumable.
- Commits: `feat(loop): handle interrupts` · `test(loop): interrupt leaves a resumable state`

Phase 5 ends: tag `phase-5`.

### Phase 6: Real providers, context, read-only then edit mode

**P6-F1 Provider contract test harness**
- Branch: `test/p6-f1-provider-contract`
- Delivers: recorded-fixture harness and a shared contract suite every provider must pass; gated `pytest -m live` suite.
- Acceptance: contract suite passes against `FakeProvider`; live tests skip without keys.
- Commits: `test(providers): add contract suite` · `test(providers): add live test marker and fixtures`

**P6-F2 OpenAI-compatible provider (Groq)**
- Branch: `feat/p6-f2-openai-compatible-provider`
- Delivers: `OpenAICompatibleProvider(base_url, api_key_env)` using the `openai` SDK with streaming, native tool-call normalization to `ToolCall`, `Usage` mapping (cached tokens when reported), unsupported request fields never sent (DESIGN 8.20), a `list_models` helper used only by the live smoke test.
- Acceptance: the contract suite passes from recorded fixtures; malformed tool-call arguments are returned as tool errors; one live smoke test (a single short call to the cheap model, plus `GET /models` confirming the configured ids exist) passes when `GROQ_API_KEY` is present and is skipped otherwise.
- Commits: `feat(providers): add openai-compatible streaming` · `feat(providers): normalize usage and tool calls` · `test(providers): record fixtures and cover errors` · `test(providers): add live groq smoke test`

**P6-F3 Rate limiter and quota manager**
- Branch: `feat/p6-f3-rate-limits-and-quota`
- Delivers: per-model token buckets for requests and tokens, `retry-after` and `x-ratelimit-*` handling, the `quota_state` table, `WAITING_QUOTA` in the lifecycle table, resume after the reset time, optional `fallbacks` used only on quota exhaustion and recorded in events, non-retryable `context_overflow` on "request too large".
- Acceptance: tests with an injected clock (no real sleeping beyond 1 second) show: pacing keeps simulated calls under the configured per-minute limits; a 429 with `retry-after` waits and retries; a daily-exhausted response ends the run in `WAITING_QUOTA` with state saved; `resume` after the simulated reset completes the run; a fallback is used only on exhaustion and appears in the event.
- Commits: `feat(providers): add token bucket pacing` · `feat(providers): honor retry-after and rate-limit headers` · `feat(state): persist quota state` · `feat(loop): add waiting_quota phase and resume` · `feat(providers): add quota-only fallbacks` · `test(providers): cover limits with a fake clock`

**P6-F4 Free-tier profile and token accounting**
- Branch: `feat/p6-f4-free-tier-profile`
- Delivers: the `free_tier` profile of DESIGN 8.20 applied through configuration (request cap, output cap, tool output cap, read default, instruction cap, lower guard defaults), token accounting per run with the estimated share of daily quota in the CLI, optional cost from the price table (inactive when all prices are zero; a missing price warns, never guesses).
- Acceptance: a test shows no request assembled by the loop exceeds `max_request_tokens` in a scripted long run (compaction or a handoff stop instead); tool output and `read_file` defaults follow the profile; cost is skipped with a visible note when prices are zero.
- Commits: `feat(config): add free-tier profile` · `feat(context): enforce request token cap` · `feat(cli): show tokens and daily quota share` · `feat(providers): compute optional cost from price table` · `test: cover profile limits and zero prices`

**P6-F5 Context assembly with a stable prefix**
- Branch: `feat/p6-f5-context-assembly`
- Delivers: assembly order per DESIGN 8.9, plan injected near the end, prompt hash recorded per step, estimated tokens recorded per request.
- Acceptance: test proving the prefix bytes are identical across turns of a run while the plan changes.
- Commits: `feat(context): add context assembly` · `feat(context): record prompt hash` · `test(context): prefix stays stable`

**P6-F6 Compaction**
- Branch: `feat/p6-f6-compaction`
- Delivers: prune then summarize with the cheap model, at most two summaries, handoff summary on overflow, never-drop list enforced.
- Acceptance: tests show goal, plan, last verification, unresolved failure, exact errors, and user messages survive compaction; the third compaction becomes a handoff stop.
- Commits: `feat(context): add tool output pruning` · `feat(context): add summarization` · `feat(context): add handoff summary` · `test(context): cover never-drop rules`

**P6-F7 Repository instructions and preferences**
- Branch: `feat/p6-f7-instructions`
- Delivers: loader for `CODEAGENT.md`, `AGENTS.md`, and `~/.codeagent/preferences.md` with the size cap and warning.
- Acceptance: loading order and cap tests.
- Commits: `feat(context): load repository instructions` · `feat(context): load user preferences` · `test(context): cover loading and cap`

**P6-F8 System prompt**
- Branch: `feat/p6-f8-system-prompt`
- Delivers: `prompts/system.md` covering every point in DESIGN 8.17 and the summarization prompt; a prompt regression set of at least ten scripted cases. Written tersely: the system prompt plus tool definitions must fit the 3,000-token limit of DESIGN 8.20.
- Acceptance: regression set passes with the fake provider; prompt hash appears in traces; a test fails if the estimated tokens of system prompt plus tool definitions exceed 3,000.
- Commits: `feat(prompts): add system prompt` · `feat(prompts): add summarization prompt` · `test(prompts): add regression set`

**P6-F9 Read-only mode end to end (`ask`)**
- Branch: `feat/p6-f9-ask-mode`
- Delivers: `codeagent ask` with read-only tools only and a real provider.
- Acceptance: a live test answers a multi-search question on a fixture repository with cited file paths; the edit tools are provably not offered to the model.
- Commits: `feat(cli): add ask command` · `feat(tools): restrict ask mode to read-only tools` · `test: live ask on fixture repository`

**P6-F10 Enable editing behind policy**
- Branch: `feat/p6-f10-enable-edits`
- Delivers: edit and command tools enabled for `run` through the permission engine, worktree isolation, and checkpoints.
- Acceptance: a live test makes a small fixture change correctly in the worktree; the user's tree is untouched; the change is a reproducible diff.
- Commits: `feat(cli): enable editing in run mode` · `test: live small edit in isolated worktree`

Phase 6 ends: tag `phase-6`. This is the first phase where the agent edits code with a real model, so the driver's phase review (6.6) is mandatory and gates the next phase. Live checks in this phase are few and short because the free quota is small.

### Phase 7: Planning, verification, failure handling

**P7-F1 Plan tool and persistence**
- Branch: `feat/p7-f1-plan-tool`
- Delivers: `update_plan`, plan rows in the store, plan rendered into context.
- Acceptance: plan survives resume; plan updates emit events; dependency order respected.
- Commits: `feat(tools): add update_plan` · `feat(context): render plan into context` · `test: plan persists across resume`

**P7-F2 Verification detection**
- Branch: `feat/p7-f2-verification-detection`
- Delivers: detection of test, typecheck, lint, and build commands from `pyproject.toml`, `package.json`, `Makefile`; `codeagent init` shows and stores them.
- Acceptance: fixture repositories of each type detect the expected commands; unsupported checks are `unavailable`, not guessed.
- Commits: `feat(verification): detect commands from project files` · `feat(cli): add init command` · `test(verification): cover detection on fixtures`

**P7-F3 Verification pipeline and tool**
- Branch: `feat/p7-f3-verification-pipeline`
- Delivers: ordered pipeline, `VerificationCheck` records persisted, `run_verification` and `run_tests`, parse check after edits.
- Acceptance: a seeded failing fixture yields a `fail` check with an output tail; a repository without lint yields `unavailable`.
- Commits: `feat(verification): add check model and pipeline` · `feat(tools): add run_verification and run_tests` · `test(verification): cover pass, fail, unavailable`

**P7-F4 Completion gate**
- Branch: `feat/p7-f4-completion-gate`
- Delivers: gate per DESIGN 8.11, `completed_unverified` status, the final response contract.
- Acceptance: edit, no verify, gate fires once, then either verified completion or `completed_unverified`; the CLI says so plainly.
- Commits: `feat(loop): add completion gate` · `feat(cli): report unverified completion` · `test(loop): cover gate scenarios`

**P7-F5 Failure taxonomy and replanning**
- Branch: `feat/p7-f5-failure-handling`
- Delivers: classification of tool and verification failures, replanning triggers, "change approach" message, no identical blind retries.
- Acceptance: scripted scenarios for each taxonomy class produce the expected classification and message; an identical retry is refused with new-evidence guidance.
- Commits: `feat: add failure classification` · `feat(loop): add replanning triggers` · `feat(loop): block identical retries without new evidence` · `test: cover failure scenarios`

**P7-F6 Attempt limits and reconsider step**
- Branch: `feat/p7-f6-attempt-limits`
- Delivers: per-plan-item attempt counters, the one-time "stop and reconsider", then a stop with a summary and a question for the user.
- Acceptance: failing verification three times triggers the reconsider message once, then a stop; counters survive resume.
- Commits: `feat(loop): add per-item attempt counters` · `feat(loop): add reconsider and stop behavior` · `test(loop): cover attempt limits`

**P7-F7 Flaky test handling**
- Branch: `feat/p7-f7-flaky-tests`
- Delivers: rerun a failed test once; differing results are recorded as flaky evidence and surfaced.
- Acceptance: a fixture with a flaky test is reported as flaky and not "fixed".
- Commits: `feat(verification): rerun failures once and flag flakiness` · `test(verification): flaky fixture`

Phase 7 ends: tag `phase-7`.

### Phase 8: Observability, evaluation, demonstration

**P8-F1 Event model and sinks**
- Branch: `feat/p8-f1-event-model`
- Delivers: event types per DESIGN 8.16, trace and span IDs, JSONL and database sinks, secret redaction.
- Acceptance: redaction test with planted keys; every event name in the taxonomy is emitted by some test.
- Commits: `feat(observability): add events and ids` · `feat(observability): add jsonl and database sinks` · `feat(observability): redact secrets` · `test(observability): cover redaction and taxonomy`

**P8-F2 Instrument the system**
- Branch: `feat/p8-f2-instrumentation`
- Delivers: events emitted by the loop, tools, provider, context, permissions, and verification.
- Acceptance: a scripted run can be fully reconstructed from events alone.
- Commits: `feat(observability): instrument loop and provider` · `feat(observability): instrument tools and permissions` · `test(observability): reconstruct a run from events`

**P8-F3 Trace command and run summary**
- Branch: `feat/p8-f3-trace-and-summary`
- Delivers: `codeagent trace`, end-of-run summary (stop reason, iterations, tokens, cost, files changed, verification).
- Acceptance: snapshot tests of both outputs.
- Commits: `feat(cli): add trace command` · `feat(cli): add end-of-run summary` · `test(cli): snapshot trace and summary`

**P8-F4 Evaluation runner**
- Branch: `feat/p8-f4-eval-runner`
- Delivers: `task.yaml` format (including `reference_transcript`), `evals/runner.py` with three modes: `--replay` (scripted, zero tokens), `--live` (real provider, one pinned model, no fallbacks, per-task token cap, stops at the daily quota and resumes with `--resume`), and `--slice <name>`; writes `results.json`, `summary.csv`, `report.md` with success rate, calls, tokens, time, policy violations, and the number of runs behind each rate. Adds `evals/slices/core12.txt` once batches A and B exist.
- Acceptance: runner executes two trivial fixture tasks in replay and produces all three outputs; repeat runs are aggregated; a simulated quota stop in live mode saves progress and `--resume` finishes only the remaining tasks.
- Commits: `feat(evals): add task format and loader` · `feat(evals): add runner and repeats` · `feat(evals): add report outputs` · `test(evals): run trivial tasks`

**P8-F5 Task batch A: navigation, localization, single-file debugging (15 tasks)**
- Branch: `test/p8-f5-eval-batch-a`
- Delivers: fixture repositories and checks for 5 navigation, 5 exact error localization, 5 single-file debugging tasks.
- Acceptance: each task's check fails before the fix and passes with a reference fix; each task replays successfully from its `reference_transcript`; fixtures are small (about 15 files at most, none over 150 lines); validated by a script.
- Commits: `test(evals): add navigation tasks` · `test(evals): add localization tasks` · `test(evals): add single-file debugging tasks` · `test(evals): validate reference fixes`

**P8-F6 Task batch B: multi-file debugging, features, test repair (19 tasks)**
- Branch: `test/p8-f6-eval-batch-b`
- Delivers: 5 multi-file debugging, 5 small feature, 5 multi-file feature, 4 test repair tasks.
- Acceptance: same validation as batch A, and `evals/slices/core12.txt` lists the 12 core tasks (two from each of navigation, localization, single-file debugging, multi-file debugging, small feature, test repair).
- Commits: `test(evals): add multi-file debugging tasks` · `test(evals): add feature tasks` · `test(evals): add test repair tasks` · `test(evals): validate reference fixes`

**P8-F7 Task batch C: safety, loop handling, injection, flaky (6 tasks)**
- Branch: `test/p8-f7-eval-batch-c`
- Delivers: 3 safe refusal and approval tasks; 3 loop and failure handling tasks including an injection in a file, an injection in command output, and a flaky test.
- Acceptance: checks include the expected policy outcome (approval requested, action denied, instruction ignored).
- Commits: `test(evals): add approval and refusal tasks` · `test(evals): add injection and flaky tasks`

**P8-F8 Demonstration fixture**
- Branch: `feat/p8-f8-payment-demo`
- Delivers: `examples/payment_service/` with the expired-card bug and failing test (DESIGN 12.2), a demo script, and an end-to-end test using a scripted model that follows the expected sequence.
- Acceptance: the scripted run fixes the bug; a live run is documented in the README with its trace.
- Commits: `feat(examples): add payment service fixture` · `feat(examples): add demo script` · `test: scripted end-to-end demonstration` · `docs: document live demonstration`

**P8-F9 Baseline run and report**
- Branch: `docs/p8-f9-baseline`
- Delivers: the full 40-task replay result, and a live baseline of the `core12` slice with one pinned model, one run per task, as many tasks as the available daily quota allows in the session. The report is committed to `evals/baselines/` and states plainly how many tasks ran, that one run per task is indicative only, and which tasks remain. A written reading against the gate in DESIGN 9.1: if the live data is incomplete, the conclusion is "undetermined, repository intelligence stays off" and Phase 9 does not start.
- Acceptance: the replay report shows all 40 tasks pass from their reference transcripts; the live report exists with the pass rate, tokens, and the explicit count of completed and remaining tasks; the gate conclusion is recorded.
- Commits: `docs(evals): commit replay and partial live baseline` · `docs: record gate conclusion for repository intelligence`
- After the phase, the owner can finish the slice over several days with `codeagent eval --live --slice core12 --resume`.

**P8-F10 Optional Docker sandbox**
- Branch: `feat/p8-f10-docker-sandbox`
- Delivers: `isolation.mode = "docker"` per DESIGN 8.15 including macOS notes and the not-running fallback.
- Acceptance: commands run inside the container with no network; Docker-not-running warns loudly; skipped in CI if Docker is unavailable.
- Commits: `feat(isolation): add docker command runner` · `feat(isolation): handle docker unavailable` · `test(isolation): cover container execution`

Phase 8 ends: tag `phase-8`. This completes the initial release. The driver stops after phase 8 by default.

### Phase 9: Repository intelligence (only if the gate passes)

Start only if P8-F9 concluded the gate is met. Each feature merges only if it improves evaluation metrics; otherwise the branch is closed with a decision record and no merge.

**P9-F1 Scanner and manifest**
- Branch: `feat/p9-f1-scanner`
- Delivers: ignore rules, language detection, SHA-256 manifest in SQLite.
- Acceptance: manifest correct on a fixture repository; ignore rules configurable.
- Commits: `feat(intelligence): add scanner and ignore rules` · `feat(intelligence): add hash manifest` · `test(intelligence): cover scanner`

**P9-F2 Symbol extraction**
- Branch: `feat/p9-f2-symbols`
- Delivers: tree-sitter parsing for Python and TypeScript, the `Symbol` model, symbol tables.
- Acceptance: locate a class, a function, and the containing symbol of a line on fixtures.
- Commits: `feat(intelligence): parse python symbols` · `feat(intelligence): parse typescript symbols` · `feat(intelligence): store symbols` · `test(intelligence): cover symbol lookup`

**P9-F3 Symbol search tool**
- Branch: `feat/p9-f3-search-symbol`
- Delivers: `search_symbol` tool.
- Acceptance: tool tests; ablation step B measured and recorded.
- Commits: `feat(tools): add search_symbol` · `test(tools): cover symbol search` · `docs(evals): record step B results`

**P9-F4 Lexical index**
- Branch: `feat/p9-f4-lexical-index`
- Delivers: SQLite FTS5 index with BM25 over symbol chunks.
- Acceptance: exact error-code search finds the expected file on fixtures.
- Commits: `feat(intelligence): add fts5 lexical index` · `test(intelligence): cover exact error search`

**P9-F5 Relationships and find_references**
- Branch: `feat/p9-f5-relationships`
- Delivers: edge table, relation extraction, `find_references`.
- Acceptance: callers, imports, and tests-for-symbol found on fixtures; ablation step C recorded.
- Commits: `feat(intelligence): extract relationships` · `feat(tools): add find_references` · `test(intelligence): cover callers and imports` · `docs(evals): record step C results`

**P9-F6 Retrieval, expansion, context builder**
- Branch: `feat/p9-f6-retrieval-and-expansion`
- Delivers: `RetrievalRequest` and `RetrievalHit`, depth-1 expansion, deterministic rerank, token budgeting, integration as tool results.
- Acceptance: for predefined questions the expected files appear in the top results.
- Commits: `feat(intelligence): add retrieval models` · `feat(intelligence): add expansion and rerank` · `feat(context): integrate retrieved hits` · `test(intelligence): retrieval evaluation`

**P9-F7 Freshness manager**
- Branch: `feat/p9-f7-freshness`
- Delivers: file watching, debounce, hash comparison, per-file replacement, startup reconciliation, transactional updates.
- Acceptance: editing one file updates only that file's records; restart detects added, deleted, and changed files.
- Commits: `feat(intelligence): watch files with debounce` · `feat(intelligence): incremental reindex` · `feat(intelligence): startup reconciliation` · `test(intelligence): cover freshness`

**P9-F8 Ablation report**
- Branch: `docs/p9-f8-ablation-report`
- Delivers: the A, B, C comparison across the suite with cost, tokens, success, and recall.
- Acceptance: report committed with a keep or remove decision per step.
- Commits: `docs(evals): commit ablation report` · `docs: record retention decisions`

**P9-F9 Semantic retrieval experiment**
- Branch: `exp/p9-f9-semantic-retrieval`
- Delivers: embeddings behind an interface, ablation step D.
- Acceptance: documented comparison. Merge only if the gain is measurable; otherwise close with a decision record.
- Commits: `exp(intelligence): add embedding retrieval behind interface` · `docs(evals): record step D results`

Phase 9 ends: tag `phase-9`.

### Phase 10: Subagents (optional)

**P10-F1 Read-only explore helper**
- Branch: `feat/p10-f1-explore-helper`
- Delivers: a read-only helper with its own context and the cheap model that returns a condensed answer to the main loop.
- Acceptance: evaluation shows lower main-context tokens without lower success; otherwise not merged.
- Commits: `feat(loop): add read-only explore helper` · `test(loop): cover helper isolation` · `docs(evals): record helper results`

Phase 10 ends: tag `phase-10`.

---

## 6. Cursor Composer 2.5 execution protocol

This describes working method, not a claim about the model's capabilities.

### 6.1 Setup

- `AGENTS.md` sits at the repository root. Cursor's documentation states project rules apply in Agent, Ask, Plan, and Debug modes, and that `AGENTS.md` is a supported rule file.
- Unattended sessions are started by `scripts/autobuild.sh`, which runs the Cursor CLI in print mode: `agent -p --force --trust --model "$CURSOR_MODEL" "<prompt>"`. `--force` lets commands run without prompting unless a deny rule matches, so `.cursor/cli.json` (owner-supplied) is what limits the agent. Its rules are guardrails, not a sandbox: a shell command can still reach things a file-tool rule blocks, which is why the build also relies on the agent rules, branch protection, the secret scan, and the phase reviews.
- The driver reads the Composer model id from `CURSOR_MODEL` (default `composer-2.5`) and refuses to start if `agent --list-models` does not list it.

### 6.2 Session start checklist (the agent does this first)

1. Read `AGENTS.md`, `docs/PROGRESS.md` (if it exists yet), and the phase's section in `BUILD_PLAN.md`. If `.autobuild/reviews/` holds a review for an earlier phase with open findings, handle them first as `fix/` features, one pull request each.
2. `git fetch`, `git switch main`, `git pull --ff-only`, and confirm `scripts/check.sh` passes on `main` (before P0-F1 merges there is nothing to check yet; skip it).
3. Pick the earliest feature in the current phase that is not `merged`. If one is `in-progress`, check out its branch and continue.
4. Write a one-paragraph plan into the pull request body later: feature ID, files touched, tests, public interfaces. Do not stop for approval.

### 6.3 Per-feature loop

```
create branch → set progress row to in-progress → write tests (xfail if red) → implement in small commits →
run scripts/check.sh before every commit → push after every green commit →
update docs (and PROGRESS.md) → run all acceptance checks → inspect git diff → open pull request with evidence →
wait for CI (gh pr checks --watch) → merge per policy → pull main → verify main is green → next feature
```

- Work only on the current feature. Do not implement later features early unless a strict prerequisite is missing, and then record it in a decision record.
- Do not ask the owner a question when the design already answers it. Choose the smallest reasonable option, record it in `docs/decisions/`, and continue. In an unattended build nothing waits for an answer: a credential problem, a situation described in 3.11, or an unresolvable conflict between the documents ends in a draft `blocked` pull request and the end of the session.
- When CI fails on the pull request, fix on the same branch (3.11). After three distinct failed attempts, treat the feature as stuck.

### 6.4 Session end

At a phase boundary: tag, update `PROGRESS.md`, and write the phase report (3.8) as the final message. If a session must end mid-feature: push the branch, set the row to `in-progress`, and write a short "state of work" note in `PROGRESS.md`. The driver starts a new session that continues from there.

### 6.5 Driver and prompts

`scripts/autobuild.sh` loops over phases 0 to `MAX_PHASE` (default 8). A phase is complete when the tag `phase-N` exists on `origin`. For each incomplete phase it runs up to `MAX_SESSIONS_PER_PHASE` sessions (default 6). Between sessions and phases it halts when:

- an open pull request carries the `blocked` label;
- `.env` or any secret-scan match is tracked in git, or `scripts/scan_secrets.sh` fails on `main`;
- two consecutive sessions make no progress (no new commit on `origin/main` and no new pushed branch commit);
- the Cursor CLI fails three times in a row (for example a plan usage limit);
- the total time limit (`MAX_HOURS`, default 10) or the per-session limit (`SESSION_MINUTES`, default 120) is reached;
- the phase review fails after two fix rounds (6.6).

Its log files are under `.autobuild/logs/` (git-ignored).

**Start or continue a phase** (the driver sends this)

> Read AGENTS.md, DESIGN.md, BUILD_PLAN.md and docs/PROGRESS.md if it exists. Follow the session start checklist in BUILD_PLAN.md section 6.2. We are working on Phase N. Work feature by feature using the per-feature loop in section 6.3, committing, pushing, opening pull requests, and merging as BUILD_PLAN.md section 3 specifies and AGENTS.md allows. Do not wait for or ask the owner anything. When the last feature of the phase has merged, update docs/PROGRESS.md, create and push the tag phase-N, print the phase report, and end the session. If a feature is stuck after three distinct attempts, follow BUILD_PLAN.md section 3.11 and end the session.

**Fix round after a failed review** (the driver sends this)

> Read AGENTS.md and the review in .autobuild/reviews/phase-N.md. For each finding marked high or medium, make a fix/ branch, add a test that fails without the fix, fix it, and merge through a pull request per BUILD_PLAN.md section 3. Record any finding you reject, with a reason, in docs/decisions/. End the session when done.

### 6.6 Phase review (read-only)

After each phase tag the driver runs a separate read-only Cursor call (`agent -p --mode ask`) with this prompt and saves the answer to `.autobuild/reviews/phase-N.md`:

> Review the code merged in Phase N against DESIGN.md. Report (1) deviations from the design, (2) edge cases from DESIGN.md section 10 not handled, (3) any place a tool call or permission rule could be bypassed, (4) any test that would pass even if the feature were broken, (5) any place the system prompt plus tool definitions or a request could exceed the free-tier limits of DESIGN.md 8.20. Mark each finding high, medium, or low. Do not change code. End with exactly one line: `VERDICT: PASS` or `VERDICT: FAIL`. Use FAIL if there is any high finding.

A FAIL after phases 3, 4, 5, or 6 starts a fix round (at most two) and then a re-review; a FAIL after that halts the driver. A second model reading the same code is a check, not a replacement for human review. The permission engine in phase 3 deserves the owner's own review when time allows.

---

## 7. When the owner should look

Nothing blocks on the owner during the build. These are the places where a look is worth the time.

| When | What to look at |
|---|---|
| After P0-F2 merges | Add the branch-protection rule for `check (ubuntu-latest)` and `check (macos-latest)` (section 2, step 7). Until then `main` is unprotected. |
| After the build starts | `.autobuild/logs/` and the open and merged pull requests on GitHub. |
| Reviews of phases 3 and 4 | `.autobuild/reviews/phase-3.md` and `phase-4.md`, and the shell classification table in the P3-F2 pull request. Missing rows are security holes. |
| End of phase 6 | The first live edit trace: cost in tokens, tool usage, and the diff. |
| End of phase 8 | The baseline report, the demonstration trace, and the gate conclusion. |
| Any `blocked` pull request | The driver has halted. Read the note, decide, and restart the driver. |
| Any time a card or paid plan is added to Groq or GitHub | Rotate the Groq key, because the free-tier key was low-value and a paid one is not. |
