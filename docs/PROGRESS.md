# Build progress

Phase 0 is in progress. Later phases remain unstarted.

| ID | Title | Branch | Status | PR | Merge commit |
|---|---|---|---|---|---|
| P0-F1 | Project skeleton and tooling | `chore/p0-f1-project-skeleton` | merged | [#1](https://github.com/smadduri9/codeagent/pull/1) | `1d27bab86644a332b6c82cc5a6f7a5f6e08b0a3c` |
| P0-F2 | CI, pull request template, secret scan | `chore/p0-f2-ci-and-templates` | merged | [#2](https://github.com/smadduri9/codeagent/pull/2) | `03d1c778ed85e8adfe397ab9f4c3abc855ebd5f4` |
| P0-F3 | Progress file and decision records | `docs/p0-f3-progress-and-decisions` | in-progress | — | — |
| P0-F4 | Layered configuration | `feat/p0-f4-config-loader` | todo | — | — |
| P1-F1 | Message, tool-call, and usage types | `feat/p1-f1-core-types` | todo | — | — |
| P1-F2 | Provider protocol and FakeProvider | `feat/p1-f2-fake-provider` | todo | — | — |
| P1-F3 | Tool registry | `feat/p1-f3-tool-registry` | todo | — | — |
| P1-F4 | Run lifecycle | `feat/p1-f4-run-lifecycle` | todo | — | — |
| P1-F5 | Agent loop with iteration guard | `feat/p1-f5-agent-loop` | todo | — | — |
| P1-F6 | Repeat and denial-streak guards | `feat/p1-f6-loop-guards` | todo | — | — |
| P1-F7 | CLI run command with streaming output | `feat/p1-f7-cli-run` | todo | — | — |
| P2-F1 | Workspace boundary helper | `feat/p2-f1-workspace-paths` | todo | — | — |
| P2-F2 | read_file and list_dir | `feat/p2-f2-read-and-list` | todo | — | — |
| P2-F3 | glob and grep | `feat/p2-f3-glob-grep` | todo | — | — |
| P2-F4 | write_file and edit_file | `feat/p2-f4-write-and-edit` | todo | — | — |
| P2-F5 | move_path and delete_path | `feat/p2-f5-move-and-delete` | todo | — | — |
| P3-F1 | Risk levels, path and secret rules | `feat/p3-f1-risk-and-path-rules` | todo | — | — |
| P3-F2 | Shell parser and classifier | `feat/p3-f2-shell-classifier` | todo | — | — |
| P3-F3 | Policy gate in the loop | `feat/p3-f3-policy-gate` | todo | — | — |
| P3-F4 | Approval UI and single-use approvals | `feat/p3-f4-approvals` | todo | — | — |
| P3-F5 | Untrusted output wrapping | `feat/p3-f5-untrusted-content` | todo | — | — |
| P3-F6 | Security suite | `test/p3-f6-security-suite` | todo | — | — |
| P4-F1 | run_command (argument array) | `feat/p4-f1-run-command` | todo | — | — |
| P4-F2 | bash (shell string) | `feat/p4-f2-bash-tool` | todo | — | — |
| P4-F3 | Git wrapper and read-only git tools | `feat/p4-f3-git-tools` | todo | — | — |
| P4-F4 | Worktree isolation with branch fallback | `feat/p4-f4-worktree-isolation` | todo | — | — |
| P4-F5 | Checkpoints, rollback, final diff | `feat/p4-f5-checkpoints-rollback` | todo | — | — |
| P4-F6 | Platform notes and cross-OS tests | `docs/p4-f6-platform-notes` | todo | — | — |
| P5-F1 | SQLite store and migrations | `feat/p5-f1-sqlite-store` | todo | — | — |
| P5-F2 | Persist the run | `feat/p5-f2-persist-run` | todo | — | — |
| P5-F3 | Resume | `feat/p5-f3-resume` | todo | — | — |
| P5-F4 | Budgets and graceful exhaustion | `feat/p5-f4-budgets` | todo | — | — |
| P5-F5 | Interrupt handling | `feat/p5-f5-interrupts` | todo | — | — |
| P6-F1 | Provider contract test harness | `test/p6-f1-provider-contract` | todo | — | — |
| P6-F2 | OpenAI-compatible provider (Groq) | `feat/p6-f2-openai-compatible-provider` | todo | — | — |
| P6-F3 | Rate limiter and quota manager | `feat/p6-f3-rate-limits-and-quota` | todo | — | — |
| P6-F4 | Free-tier profile and token accounting | `feat/p6-f4-free-tier-profile` | todo | — | — |
| P6-F5 | Context assembly with a stable prefix | `feat/p6-f5-context-assembly` | todo | — | — |
| P6-F6 | Compaction | `feat/p6-f6-compaction` | todo | — | — |
| P6-F7 | Repository instructions and preferences | `feat/p6-f7-instructions` | todo | — | — |
| P6-F8 | System prompt | `feat/p6-f8-system-prompt` | todo | — | — |
| P6-F9 | Read-only mode end to end (`ask`) | `feat/p6-f9-ask-mode` | todo | — | — |
| P6-F10 | Enable editing behind policy | `feat/p6-f10-enable-edits` | todo | — | — |
| P7-F1 | Plan tool and persistence | `feat/p7-f1-plan-tool` | todo | — | — |
| P7-F2 | Verification detection | `feat/p7-f2-verification-detection` | todo | — | — |
| P7-F3 | Verification pipeline and tool | `feat/p7-f3-verification-pipeline` | todo | — | — |
| P7-F4 | Completion gate | `feat/p7-f4-completion-gate` | todo | — | — |
| P7-F5 | Failure taxonomy and replanning | `feat/p7-f5-failure-handling` | todo | — | — |
| P7-F6 | Attempt limits and reconsider step | `feat/p7-f6-attempt-limits` | todo | — | — |
| P7-F7 | Flaky test handling | `feat/p7-f7-flaky-tests` | todo | — | — |
| P8-F1 | Event model and sinks | `feat/p8-f1-event-model` | todo | — | — |
| P8-F2 | Instrument the system | `feat/p8-f2-instrumentation` | todo | — | — |
| P8-F3 | Trace command and run summary | `feat/p8-f3-trace-and-summary` | todo | — | — |
| P8-F4 | Evaluation runner | `feat/p8-f4-eval-runner` | todo | — | — |
| P8-F5 | Task batch A: navigation, localization, single-file debugging (15 tasks) | `test/p8-f5-eval-batch-a` | todo | — | — |
| P8-F6 | Task batch B: multi-file debugging, features, test repair (19 tasks) | `test/p8-f6-eval-batch-b` | todo | — | — |
| P8-F7 | Task batch C: safety, loop handling, injection, flaky (6 tasks) | `test/p8-f7-eval-batch-c` | todo | — | — |
| P8-F8 | Demonstration fixture | `feat/p8-f8-payment-demo` | todo | — | — |
| P8-F9 | Baseline run and report | `docs/p8-f9-baseline` | todo | — | — |
| P8-F10 | Optional Docker sandbox | `feat/p8-f10-docker-sandbox` | todo | — | — |
| P9-F1 | Scanner and manifest | `feat/p9-f1-scanner` | todo | — | — |
| P9-F2 | Symbol extraction | `feat/p9-f2-symbols` | todo | — | — |
| P9-F3 | Symbol search tool | `feat/p9-f3-search-symbol` | todo | — | — |
| P9-F4 | Lexical index | `feat/p9-f4-lexical-index` | todo | — | — |
| P9-F5 | Relationships and find_references | `feat/p9-f5-relationships` | todo | — | — |
| P9-F6 | Retrieval, expansion, context builder | `feat/p9-f6-retrieval-and-expansion` | todo | — | — |
| P9-F7 | Freshness manager | `feat/p9-f7-freshness` | todo | — | — |
| P9-F8 | Ablation report | `docs/p9-f8-ablation-report` | todo | — | — |
| P9-F9 | Semantic retrieval experiment | `exp/p9-f9-semantic-retrieval` | todo | — | — |
| P10-F1 | Read-only explore helper | `feat/p10-f1-explore-helper` | todo | — | — |

## Session evidence

- P0-F1: PR #1 already merged; bootstrap exception recorded in decision 0001.
- P0-F2: PR #2 passed both CI checks (run 37187219038); post-merge
  scripts/check.sh passed with 15 tests. Secret scan passed. No live tests.
- Owner follow-up: configure required CI checks per BUILD_PLAN section 2.
