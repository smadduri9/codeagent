# Eval expansion plan

Status: proposed, 2026-10-14. Owner approval needed before any paid run.

## Why

The 30-task SWE-bench Lite subset cannot measure harness changes. Identical Haiku runs flipped 6 of 30 outcomes. A simulation fitted to those runs (about 6 tasks always solved, 12 coin flips, 12 never solved) gives a single 30-task run an 8% chance of detecting a real +3-task improvement. An audit of the 66 failed task-runs puts the harness-fixable share at roughly 1 to 3 tasks per run. Every change we care about is smaller than the noise at n = 30.

The audit also found that the completion gate never ran on the policy path (fixed in #82). The published numbers were measured with the gate inert, so they are not a valid baseline for anything that follows.

## What the field treats as a golden eval for coding agents

- **Grade the end state, by execution.** Hidden tests that fail before the reference fix and pass after it, run after the agent finishes. Do not grade the tool-call sequence; it punishes valid alternative paths. Anthropic's agent-eval guidance and most practitioner write-ups agree on this. Read transcripts anyway, to check that the grader is fair.
- **Contamination is now the main validity problem.** OpenAI stopped reporting SWE-bench Verified in February 2026: it found test flaws behind 59.4% of 138 audited o3 failures and evidence that models recall repository details. It recommends SWE-bench Pro. SWE-rebench collects issues after model training cutoffs and runs each model five times to report variance.
- **Repeat runs, and report more than one rate.** pass@k (any of k succeeds) estimates what selection could reach. pass^k (all k succeed) measures reliability. The mean solve rate over k runs is the primary comparison metric.
- **Grow the golden set from real failures.** Each failure mode we see becomes a targeted case, so the suite tracks what actually breaks.

## Where this repo stands

| Requirement | Today |
|---|---|
| Execution-graded end state | Yes: hidden failing tests, gold test patch never shown |
| Validated tasks (fail before, pass after) | Yes, 30 of 30 |
| Enough tasks to detect +3 to +5 | No: 30 |
| Repeated runs per arm | Partly: 2 identical Haiku runs |
| Uncontaminated tasks | No: Lite predates both models' training cutoffs |
| Paired statistics, preregistered decision rule | McNemar yes; preregistration no |
| Behaviour tests in CI for the gate and finishing rules | No: replay passed 42/42 with the gate inert |

## Contamination does not block harness ablations

Contamination inflates absolute scores. It does not bias a paired comparison much: the same model with the same memorised knowledge runs both arms, so the difference between arms still reflects the harness. We can therefore keep the cheap local Lite pipeline for ablations, as long as we never report a Lite score as an absolute capability number. Use a fresh-task slice for that.

## Plan

### Tier A: behaviour cases in CI (zero tokens)

Add replay tasks that assert behaviour, not just plumbing:

- edit then stop → exactly one verify prompt, outcome `completed_unverified`;
- edit, then a failing pytest, then stop → prompt;
- empty diff at finish → flagged;
- an edit under `tests/` → flagged.

Each fixed bug from a live run (#74, #76, #79, #82) gets a replay case.

### Tier B: SWE-Lite-100, the ablation set (paid, Haiku only)

1. Extend `evals/select_swe30.py` to take every Lite task from sympy, pytest, sphinx, pylint, flask and requests. That is 125 candidates (77 + 17 + 16 + 6 + 3 + 6).
2. Validate each with `evals/swebench_env.py`: the environment builds, the failing tests fail before the reference fix and pass after it. Expect about 100 to survive. Record the list and seed in `evals/slices/swe100.txt`.
3. **Record the pre-existing failures** in each task's target test files on the clean checkout. This is a by-product of validation. A later harness variant can give this list to the agent: the audit found 23 turns where the agent explained away a red result as "XFAIL" or "environmental".
4. **Baseline:** Haiku, 3 runs, on the commit after #82, pinned by SHA. About 300 task-runs, roughly $2.50 at the observed $0.25 per 30 tasks.
5. **Each variant:** 3 runs against the same baseline, about $2.50. Compare per-task mean solve rates with a paired sign-flip permutation test. Report the mean with a 95% CI, per-task wins and losses, pass@3, pass^3, cost per solve and median tokens per solve.
6. **Decision rule, fixed before running:** ship a variant if the mean gain is at least 3 tasks per 100 and p < 0.05. If the point estimate is positive but p ≥ 0.05, add 2 runs per arm (k = 5) once, then decide. Simulated power at about 90 tasks and k = 3: +5/30 equivalent ≈ 99%, +3/30 ≈ 68%; k = 5 brings +3 to ≈ 82%.

**Variants, in order** (from the failure audit, one change per variant):

1. Unattended bug-fix prompt: reproduce, then fix, then re-run the reproduction and nearby tests. Remove "stop and ask". Show "calls used N/20".
2. Tool output: grep with `file:line:` prefixes, `content` accepted as an alias for `lines`, head-kept truncation for grep and read_file, exit code first in `run_command` output.
3. Read-only `git diff`, `git status`, `git stash` and `pwd` allowed in eval runs.
4. Pre-existing failure list given to the agent.
5. Best-of-3 with selection by the agent's own reproduction tests (costs 3 times as much; run last).

### Tier C: fresh slice for honest absolute numbers (paid, later)

About 30 Python tasks from the newest SWE-rebench monthly split, created after both models' training cutoffs. Report this, not Lite, as the capability number in the README.

Open question: SWE-rebench and SWE-bench Pro ship x86 Docker images, and this machine is arm64. Options are an x86 CI runner, a rented VM, or rebuilding the environments with our local venv approach. Decide this before Tier C. SWE-bench Pro also needs Docker, covers several languages, and is out of scope until the Python agent is stable.

### Automated failure labels

Add a post-run script that labels every failed task-run from `state.db`. Labels come from transcript features, not from the hidden tests:

- no edit;
- no reproduction run;
- no pytest after the last edit;
- red pytest at finish;
- stopped with calls left;
- hit the call cap;
- denial-ended;
- grep errors.

Report the label counts for each arm. This tells us why a variant moved the score, not just that it moved.

## Budget

| Step | Cost |
|---|---|
| Validation (no model calls) | $0 |
| Haiku baseline, k = 3 | about $2.50 |
| Variants 1 to 4, k = 3 each | about $10 |
| Best-of-3 variant | about $7.50 |
| Optional k = 5 top-ups | about $1.70 each |

All live runs use Haiku. Sonnet only with explicit owner approval per run. Every run is capped in code with `--cap`.

## Out of scope

- Raising the 20-call limit: only 9 of 66 failures hit it.
- Memory, handoffs, goal restatement: the largest request was about 26K tokens and compaction never fired.
- Django (114 Lite tasks): it uses its own test runner. Add it later if 100 tasks prove too few.

## Sources

- OpenAI, [Why we no longer evaluate SWE-bench Verified](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)
- [SWE-Bench Pro](https://arxiv.org/pdf/2509.16941); [Scale AI harness](https://github.com/scaleapi/SWE-bench_Pro-os)
- [SWE-rebench](https://arxiv.org/pdf/2505.20411); [leaderboard dataset](https://hub.harborframework.com/datasets/swe-rebench/swe-rebench-leaderboard/latest)
- Anthropic, [Demystifying evals for AI agents](https://anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Agentless](https://arxiv.org/html/2407.01489v2) (selection with reproduction tests)
- [SWE-agent](https://arxiv.org/html/2405.15793v3) (agent-computer interface ablations)
