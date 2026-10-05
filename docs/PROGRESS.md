# Build progress

Phase 0 is complete at tag `phase-0`. Phases 1–8 initial release work is merged on
`main`. Phase 9 remains skipped (gate not met on partial live baseline). Phase 10
skipped (no eval evidence). See decision records 0007, 0008, and 0009.

| ID | Title | Branch | Status | PR | Merge commit |
|---|---|---|---|---|---|
| P0-F1 | Project skeleton and tooling | `chore/p0-f1-project-skeleton` | merged | [#1](https://github.com/smadduri9/codeagent/pull/1) | `1d27bab` |
| P0-F2 | CI, pull request template, secret scan | `chore/p0-f2-ci-and-templates` | merged | [#2](https://github.com/smadduri9/codeagent/pull/2) | `03d1c77` |
| P0-F3 | Progress file and decision records | `docs/p0-f3-progress-and-decisions` | merged | [#3](https://github.com/smadduri9/codeagent/pull/3) | `44c728a` |
| P0-F4 | Layered configuration | `feat/p0-f4-config-loader` | merged | [#4](https://github.com/smadduri9/codeagent/pull/4) | `phase-0^{commit}` |
| P1-F1 | Message, tool-call, and usage types | `feat/p1-f1-core-types` | merged | [#7](https://github.com/smadduri9/codeagent/pull/7) | `18fc84d` |
| P1-F2 | Provider protocol and FakeProvider | `feat/p1-f2-fake-provider` | merged | [#10](https://github.com/smadduri9/codeagent/pull/10) | `ee0b0df` |
| P1-F3 | Tool registry | `feat/p1-f3-tool-registry` | merged | [#12](https://github.com/smadduri9/codeagent/pull/12) | `db2a36f` |
| P1-F4 | Run lifecycle | `feat/p1-f4-run-lifecycle` | merged | [#13](https://github.com/smadduri9/codeagent/pull/13) | `71dc3ec` |
| P1-F5 | Agent loop with iteration guard | `feat/p1-f5-agent-loop` | merged | [#13](https://github.com/smadduri9/codeagent/pull/13) | `71dc3ec` |
| P1-F6 | Repeat and denial-streak guards | `feat/p1-f6-loop-guards` | merged | [#13](https://github.com/smadduri9/codeagent/pull/13) | `71dc3ec` |
| P1-F7 | CLI run command with streaming output | `feat/p1-f7-cli-run` | merged | [#13](https://github.com/smadduri9/codeagent/pull/13) | `71dc3ec` |
| P2-F1 | Workspace boundary helper | `feat/p2-f1-workspace-paths` | merged | [#14](https://github.com/smadduri9/codeagent/pull/14) | `275bb2c` |
| P2-F2 | read_file and list_dir | `feat/p2-f2-read-and-list` | merged | [#14](https://github.com/smadduri9/codeagent/pull/14) | `275bb2c` |
| P2-F3 | glob and grep | `feat/p2-f3-glob-grep` | merged | [#14](https://github.com/smadduri9/codeagent/pull/14) | `275bb2c` |
| P2-F4 | write_file and edit_file | `feat/p2-f4-write-and-edit` | merged | [#14](https://github.com/smadduri9/codeagent/pull/14) | `275bb2c` |
| P2-F5 | move_path and delete_path | `feat/p2-f5-move-and-delete` | merged | [#14](https://github.com/smadduri9/codeagent/pull/14) | `275bb2c` |
| P3-F1 | Risk levels, path and secret rules | `feat/p3-f1-risk-and-path-rules` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P3-F2 | Shell parser and classifier | `feat/p3-f2-shell-classifier` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P3-F3 | Policy gate in the loop | `feat/p3-f3-policy-gate` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P3-F4 | Approval UI and single-use approvals | `feat/p3-f4-approvals` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P3-F5 | Untrusted output wrapping | `feat/p3-f5-untrusted-content` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P3-F6 | Security suite | `test/p3-f6-security-suite` | merged | [#15](https://github.com/smadduri9/codeagent/pull/15) | `fc09141` |
| P4-F1 | run_command (argument array) | `feat/p4-f1-run-command` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P4-F2 | bash (shell string) | `feat/p4-f2-bash-tool` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P4-F3 | Git wrapper and read-only git tools | `feat/p4-f3-git-tools` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P4-F4 | Worktree isolation with branch fallback | `feat/p4-f4-worktree-isolation` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P4-F5 | Checkpoints, rollback, final diff | `feat/p4-f5-checkpoints-rollback` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P4-F6 | Platform notes and cross-OS tests | `docs/p4-f6-platform-notes` | merged | [#16](https://github.com/smadduri9/codeagent/pull/16) | `ba3b937` |
| P5-F1 | SQLite store and migrations | `feat/p5-f1-sqlite-store` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P5-F2 | Persist the run | `feat/phase-5-6-resume-budget` | merged | [#20](https://github.com/smadduri9/codeagent/pull/20) | `e7a84a5` |
| P5-F3 | Resume | `feat/phase-5-6-resume-budget` | merged | [#20](https://github.com/smadduri9/codeagent/pull/20) | `e7a84a5` |
| P5-F4 | Budgets and graceful exhaustion | `feat/phase-5-6-resume-budget` | merged | [#20](https://github.com/smadduri9/codeagent/pull/20) | `e7a84a5` |
| P5-F5 | Interrupt handling | `feat/phase-5-6-resume-budget` | merged | [#20](https://github.com/smadduri9/codeagent/pull/20) | `e7a84a5` |
| P6-F1 | Provider contract test harness | `test/p6-f1-provider-contract` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P6-F2 | OpenAI-compatible provider (Groq) | `feat/p6-f2-openai-compatible-provider` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F3 | Rate limiter and quota manager | `feat/p6-f3-rate-limits-and-quota` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F4 | Free-tier profile and token accounting | `feat/p6-f4-free-tier-profile` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F5 | Context assembly with a stable prefix | `feat/p6-f5-context-assembly` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F6 | Compaction | `feat/p6-f6-compaction` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F7 | Repository instructions and preferences | `feat/p6-f7-instructions` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F8 | System prompt | `feat/p6-f8-system-prompt` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F9 | Read-only mode end to end (`ask`) | `feat/p6-f9-ask-mode` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P6-F10 | Enable editing behind policy | `feat/p6-f10-enable-edits` | merged | [#18](https://github.com/smadduri9/codeagent/pull/18) | `83e2f03` |
| P7-F1 | Plan tool and persistence | `feat/p7-f1-plan-tool` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F2 | Verification detection | `feat/p7-f2-verification-detection` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F3 | Verification pipeline and tool | `feat/p7-f3-verification-pipeline` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F4 | Completion gate | `feat/p7-f4-completion-gate` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F5 | Failure taxonomy and replanning | `feat/p7-f5-failure-handling` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F6 | Attempt limits and reconsider step | `feat/p7-f6-attempt-limits` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P7-F7 | Flaky test handling | `feat/p7-f7-flaky-tests` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P8-F1 | Event model and sinks | `feat/p8-f1-event-model` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P8-F2 | Instrument the system | `feat/p8-f2-instrumentation` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P8-F3 | Trace command and run summary | `feat/p8-f3-trace-and-summary` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P8-F4 | Evaluation runner | `feat/p8-f4-eval-runner` | merged | [#17](https://github.com/smadduri9/codeagent/pull/17) | `3e63185` |
| P8-F5 | Task batch A (15 tasks) | `test/p8-f5-f7-eval-batches` | merged | [#19](https://github.com/smadduri9/codeagent/pull/19) | `77f406c` |
| P8-F6 | Task batch B (19 tasks) | `test/p8-f5-f7-eval-batches` | merged | [#19](https://github.com/smadduri9/codeagent/pull/19) | `77f406c` |
| P8-F7 | Task batch C (6 tasks) | `test/p8-f5-f7-eval-batches` | merged | [#19](https://github.com/smadduri9/codeagent/pull/19) | `77f406c` |
| P8-F8 | Demonstration fixture | `feat/p8-f8-payment-demo` | merged | — | `4b22201` |
| P8-F9 | Baseline run and report | `docs/p8-f9-baseline` | merged | [#22](https://github.com/smadduri9/codeagent/pull/22) | `f76771f` |
| P8-F10 | Optional Docker sandbox | `feat/p8-f10-docker-sandbox` | merged | [#24](https://github.com/smadduri9/codeagent/pull/24) | [0009](docs/decisions/0009-docker-sandbox-approach.md) |
| P9-F1 | Scanner and manifest | `feat/p9-f1-scanner` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F2 | Symbol extraction | `feat/p9-f2-symbols` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F3 | Symbol search tool | `feat/p9-f3-search-symbol` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F4 | Lexical index | `feat/p9-f4-lexical-index` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F5 | Relationships and find_references | `feat/p9-f5-relationships` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F6 | Retrieval, expansion, context builder | `feat/p9-f6-retrieval-and-expansion` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F7 | Freshness manager | `feat/p9-f7-freshness` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F8 | Ablation report | `docs/p9-f8-ablation-report` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P9-F9 | Semantic retrieval experiment | `exp/p9-f9-semantic-retrieval` | skipped | — | [0008](docs/decisions/0008-phase-9-gate-not-met.md) |
| P10-F1 | Read-only explore helper | `feat/p10-f1-explore-helper` | skipped | — | no eval evidence (gate off) |

## Session evidence

- CLI chat + streaming: branch `feat/cli-chat-streaming` — default `codeagent` / `codeagent chat` REPL, streamed run output, final answer block; `scripts/check.sh` green.
- Groq free-tier stack: PR #28 — `cheap`/`main`/`fallbacks` docs, `resolve_run_model`, k8s-hpa-benchmark example config.
- P8-F5–F7: PR #19; 40-task fixtures, `core12` slice, replay validation tests; 407+ tests green.
- P8-F8: payment fixture on `main` at `4b22201`; `tests/unit/test_payment_demo.py`.
- P8-F9: replay baseline under `evals/baselines/replay-40/`; live core12 **2/12** (feat-01, feat-02 pass); gate **not met / undetermined** per `evals/baselines/gate-conclusion.md`.
- P8-F10: merged PR #24; Docker command sandbox per decision 0009.
- Phase 9: skipped per decision 0008.
- P10-F1: skipped (no ablation baseline).

## Phase 8 report

- Scripted replay: 42/42 tasks pass (40 eval tasks + 2 harness smoke tasks).
- Live core12: not run in build session (quota preserved).
- Repository intelligence: off until live baseline satisfies DESIGN 9.1.
- Initial release scope complete except Docker sandbox (deferred).
