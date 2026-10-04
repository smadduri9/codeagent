# CodeAgent: Technical Design

A local, CLI-based autonomous coding agent. The user runs it inside a git repository and describes a goal. The agent reads and searches code, edits files, runs commands and tests, verifies its own work, and iterates until the goal is met or a budget is exhausted. Destructive and external actions require human approval.

The build process (GitHub workflow, feature-by-feature plan, Cursor Composer 2.5 protocol) is in `BUILD_PLAN.md`. Standing rules for the implementing agent are in `AGENTS.md`.

Guiding sentence: **the model reasons; deterministic software searches, executes, constrains, verifies, persists, and observes.**

---

## 1. Purpose, scope, assumptions

### 1.1 Goals

- Understand an existing codebase (brownfield) and create code from scratch (greenfield) using one loop.
- Debug issues and implement features across multiple steps.
- Autonomous for safe actions; human approval for destructive or external actions only.
- One model-provider interface. The initial release ships a single OpenAI-compatible provider and runs on Groq's free tier (section 8.20). The user picks the main model and an optional cheaper model for small internal calls; other OpenAI-compatible endpoints work by changing `base_url`.
- Resumable: a crash or Ctrl-C never loses a run.
- Verified: the agent cannot declare success without verification evidence.
- Observable: every model call, tool call, decision, edit, and cost is recorded.
- Measurable: every change can be judged against an evaluation suite.

### 1.2 Non-goals for the initial release

- Multi-user or multi-tenant operation, hosted service, web UI, IDE extension, GUI.
- Local-model inference.
- Autonomous `git push`, autonomous deployment, automatic pull-request merging by the agent itself.
- Redis, message brokers, graph databases, separate vector database services, Kubernetes.
- Multi-agent conversations. One orchestrator owns each task; bounded read-only helpers may come later.
- Browser automation.
- A semantic final-answer cache (see decision D11).
- Autonomous dependency installation without approval.

### 1.3 Assumptions

- Primary dev machine: macOS on Apple Silicon (arm64). Anything platform-dependent is called out where it applies: Docker runs inside a Linux VM on macOS, BSD vs GNU tool flags differ, and `sandbox-exec` is not relied on. Linux should work. Windows is unsupported.
- Python 3.12, `git`, and ripgrep (`rg`) are installed.
- The target repository is a git repository. If it is not, the agent offers to run `git init`, with approval.
- Single developer, single machine, one active run per repository.

---

## 2. Principles and invariants

These hold for the life of the project.

1. **Model output is a proposal.** It becomes an action only after schema validation and a policy decision.
2. **No tool executes before validation and a recorded policy decision.**
3. **No destructive action bypasses approval,** and approvals are single-use.
4. **Repository facts come from inspection,** not model memory.
5. **Command and test results are evidence,** never prose invented by the model.
6. **Task progress lives in durable state,** not only in the context window.
7. **Every edit is attributable to a task and recoverable as a diff.**
8. **Verification is part of the loop,** not a post-processing step. Code written is not work done.
9. **Failure must add evidence or change strategy.** Identical blind retries are forbidden.
10. **The system stops safely under bounded limits** (iterations, tokens, cost, time).
11. **Tool output is untrusted data.** Text inside files, web pages, or command output can never grant permissions or change the rules.
12. **Simplicity first.** Prefer the smallest implementation that meets the acceptance criteria. Do not add infrastructure because it is fashionable.

---

## 3. Key decisions

| ID | Decision | Why | Revisit when |
|---|---|---|---|
| D1 | **Agentic search first.** The model finds code with `grep`, `glob`, and `read_file` inside the loop. A code index is built only if evaluation shows search is the bottleneck (section 9). | An index adds staleness and reindex-race problems before the base loop is proven. | The baseline evaluation meets the gate in section 9.1. |
| D2 | **One loop for greenfield and brownfield.** Planning is a tool (`update_plan`), not a separate pipeline. | Same machinery. Planning simply matters more when there is no code to read. | Never expected. |
| D3 | **Native tool calling,** not a custom JSON decision schema. | Provider APIs already validate and stream tool calls. A custom schema adds repair prompts and a failure mode. | A required provider lacks usable tool calling. |
| D4 | **Deterministic permission engine.** Rules decide allow, ask, or deny. No model judges safety. | Predictable, testable, not promptable around. | Never for the core gate. A model may later suggest rules but never decide. |
| D5 | **SQLite for task state,** not flat files. | Atomic writes, no corruption, queryable for resume and evaluation. | Never expected. |
| D6 | **Isolated git worktree is the default,** with branch mode as fallback. | The user's checkout is never touched. Rollback is simple. | Worktrees are unavailable for a target repository. |
| D7 | **Exact-string `edit_file`** is the primary editing tool. New files use `write_file`. | Fewer accidental changes, smaller outputs, easy to validate. | Measured edit-failure rate is high. |
| D8 | **Two command tools.** `run_command` takes an argument array with no shell interpretation. `bash` takes a shell string and is classified, with Ask as the default. | Argument arrays avoid the hardest classification problem. The shell string is kept because agents need pipes, `cd`, and environment variables. | Evaluation shows the shell string is rarely needed. |
| D9 | **Stable prompt prefix.** System prompt and tool definitions never change mid-run. Compaction appends to history instead of rewriting the prefix. | Keeps provider prompt caching effective. | Provider caching rules change. |
| D10 | **Synchronous loop with streamed output.** Tool calls from one model turn run sequentially. | Simplest to build and test. | Profiling shows parallel read-only tools matter. |
| D11 | **No semantic answer cache.** Prompt caching only. | Answers about code go stale when files change. A hit-safe cache would need to be keyed on file hashes and would rarely hit. | Evaluation shows repeated identical questions are common. |
| D12 | **Summaries and other small internal calls use the cheap model; planning and editing use the main model.** | Cost control without hurting quality. | Evaluation shows the cheap model hurts a step. |

---

## 4. Architecture

```
                         ┌───────────────┐
                         │   CLI (Typer) │  streaming output, approval UI
                         └──────┬────────┘
                                │ goal / approvals / interrupts
                                ▼
┌───────────────────────────── Agent Loop ─────────────────────────────┐
│  1. Assemble context (ContextManager)                                │
│  2. Call model (Provider, streaming)                                 │
│  3. Text-only reply → completion gate → finish or continue           │
│  4. Each tool call: validate → PermissionEngine → (ask user) → run   │
│  5. Append truncated results; persist everything (StateStore)        │
│  6. Check guards: iterations, tokens, cost, time, repeats, interrupt │
└──────────────────────────────────────────────────────────────────────┘
     │            │             │            │            │
 Provider     Tool Registry  Permission   State Store  Isolation
 (OpenAI-     (files, search, Engine      (SQLite)     (worktree,
  compatible,  commands,     (rules)                    checkpoints)
  Groq)
               git, verify)
                     │
        Verifier · Sandbox (optional Docker) · Observability (events, cost)
        Repository intelligence (gated; section 9)
```

Dependencies point downward only. The loop depends on everything. Tools, permissions, and state do not depend on the loop.

---

## 5. Technology choices

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Fast iteration, mature parsing and tooling ecosystem |
| CLI | Typer, Rich | Typed commands, readable streaming output |
| Validation | Pydantic v2 | Tool arguments, config, state models |
| Database | SQLite (`sqlite3`, WAL mode) | Durable local state; explicit SQL |
| Code search | ripgrep subprocess wrapper | Exact and regex search |
| Git | `git` subprocess with typed wrappers | Preserves native git behavior |
| Tests | pytest | Unit, integration, evaluation harness |
| Lint, types | ruff, mypy (strict) | Fast checks the agent can run itself |
| Provider SDK | `openai` Python SDK pointed at Groq (`base_url`), behind a protocol | Groq exposes an OpenAI-compatible API with native tool calling; no vendor types leak into the loop |
| Model provider (development and evaluation) | Groq free tier | No cost; hard per-model rate and daily token limits shape the design (8.20) |
| Local secrets | `.env` (git-ignored) plus environment variables | Keeps `GROQ_API_KEY` out of the repository |
| Parsing (gated) | tree-sitter | Multi-language symbols |
| File watching (gated) | watchdog | Incremental index freshness |
| Hashing | SHA-256 | Change detection, cache keys |

Explicitly deferred: vector database, Neo4j, Redis, LangChain, LangGraph. The agent loop must be readable without a framework.

---

## 6. Repository layout

```
codeagent/
├─ AGENTS.md  DESIGN.md  BUILD_PLAN.md  README.md
├─ pyproject.toml
├─ scripts/ check.sh  scan_secrets.sh  autobuild.sh
├─ .env.example  .cursorignore  .cursor/cli.json
├─ .github/ workflows/ci.yml  pull_request_template.md
├─ docs/ PROGRESS.md  decisions/  platform-notes.md
├─ prompts/ system.md  summarize.md
├─ src/codeagent/
│  ├─ cli.py                      # Typer entrypoint, approval prompts, rendering
│  ├─ config.py                   # layered settings
│  ├─ loop.py                     # AgentLoop
│  ├─ lifecycle.py                # run phases and transition validation
│  ├─ providers/  base.py openai_compatible.py ratelimit.py quota.py fake.py
│  ├─ tools/      base.py registry.py fs.py search.py commands.py git.py
│  │              plan.py interact.py web.py verify.py
│  ├─ permissions/ engine.py shell_parse.py rules.py approvals.py untrusted.py
│  ├─ context/    manager.py compaction.py instructions.py
│  ├─ state/      store.py schema.sql migrations/
│  ├─ isolation/  worktree.py checkpoint.py
│  ├─ verification/ pipeline.py detect.py checks.py
│  ├─ failures.py                 # taxonomy, replanning triggers
│  ├─ observability/ events.py sink.py cost.py
│  └─ intelligence/               # gated, section 9
│     scanner.py symbols.py lexical.py relationships.py retrieval.py freshness.py
├─ evals/ tasks/  runner.py  baselines/
├─ examples/ payment_service/
└─ tests/ unit/ integration/ fixtures/ security/
```

---

## 7. Run lifecycle

Every run has an explicit lifecycle phase, used for status display, logging, and resume. The loop itself is the tool-call loop in 8.2. Phases do not add model calls.

```python
class RunPhase(str, Enum):
    INITIALIZING = "initializing"
    WORKING = "working"                 # model call / tool execution loop
    WAITING_APPROVAL = "waiting_approval"
    WAITING_QUOTA = "waiting_quota"     # daily or per-minute provider limit reached; state saved, resumable
    VERIFYING = "verifying"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    COMPLETED_UNVERIFIED = "completed_unverified"
    STOPPED = "stopped"                 # budget, interrupt, denial streak
    FAILED = "failed"                   # unrecoverable error
    CANCELLED = "cancelled"
```

Allowed transitions are a fixed table. An invalid transition raises an error and is logged. Every transition emits a `run.phase_changed` event.

---

## 8. Component specifications

### 8.1 Provider interface

```python
class Provider(Protocol):
    def stream(self, req: ModelRequest) -> Iterator[ModelEvent]: ...
    def count_tokens(self, messages: list[Message]) -> int: ...   # estimate is acceptable

@dataclass
class ModelRequest:
    system: str                      # stable prefix (D9)
    messages: list[Message]
    tools: list[ToolSpec]
    model: str
    max_output_tokens: int
    temperature: float = 0.0

# ModelEvent: TextDelta, ToolCallStart, ToolCallArgsDelta, ToolCallEnd, Usage, Stop(reason)
```

Requirements:

- Normalize each vendor's tool-call format into `ToolCall(id, name, args: dict)`.
- Emit `Usage(input, output, cache_read, cache_write)` for every response. Cost comes from a user-maintained price table in config. **No model names or prices in code.**
- Respect provider rate limits (8.20): pace requests client-side, honor `retry-after`, and turn an exhausted daily quota into `WAITING_QUOTA` rather than a failure.
- Retry transient failures (rate limit, server error, network) with capped exponential backoff and jitter. A provider call always happens before tool execution, so retrying never repeats a side effect.
- Malformed tool arguments from the model are returned to it as a tool error describing the schema problem. They never reach execution.
- `FakeProvider` replays a scripted list of turns. All loop tests use it. No test may touch the network.

### 8.2 Agent loop

```python
def run(goal, repo, cfg) -> RunResult:
    run = store.create_run(goal, repo, cfg)
    isolation.begin(run)                           # worktree or branch, base snapshot
    history = [user_message(goal)]
    while True:
        guard = guards.check(run)                  # iterations, tokens, cost, time, repeats, interrupt
        if guard.stop: return finish(run, guard.reason)

        ctx = context.assemble(run, history)
        reply = collect(provider.stream(ctx))
        store.record_step(run, reply)

        if not reply.tool_calls:
            gate = completion_gate(run)            # section 8.11
            if gate.ok: return finish(run, gate.status)
            history += [reply.message, gate.message]
            continue

        results = []
        for call in reply.tool_calls:
            args = tools.validate(call)            # schema errors become tool errors
            decision = permissions.decide(call, args, run)
            store.record_decision(run, call, decision)          # before execution, always
            if decision is Ask: decision = cli.ask_user(call)   # approve once / deny / allow for session
            result = tools.run(call, args) if decision is Allow else denied(call, decision)
            results.append(wrap_untrusted(truncate(result)))
            store.record_tool(run, call, result)
        history += [reply.message, tool_results_message(results)]
```

Workflow the system prompt asks for: understand, plan (for multi-step work), inspect, act, observe, verify, then replan, continue, complete, or fail. That workflow is guidance in the prompt, not a separate state machine. A debugging request should first reproduce the failure where practical.

### 8.3 Tools

Every tool returns `ToolResult(ok, summary, content, truncated, exit_code?, duration_ms)`. Content is capped (default 30,000 characters; the free-tier profile in 8.20 lowers this to 8,000) with an explicit marker such as `[truncated: 120,431 chars total; use offset/limit or narrow the search]`. Command output keeps the tail, because errors are usually last.

| Tool | Args | Behavior |
|---|---|---|
| `read_file` | `path`, `offset?`, `limit?` | Line-numbered. Rejects binary files and files over a size cap. Default 2,000 lines. |
| `list_dir` | `path` | Non-recursive. Respects `.gitignore`. |
| `glob` | `pattern` | Respects `.gitignore`, sorted by modification time, capped. |
| `grep` | `pattern`, `path?`, `glob?`, `context?`, `output_mode` | Wraps `rg`. Modes: files, lines, count. Capped. |
| `write_file` | `path`, `content` | **New files only.** Fails if the file exists. Creates parent directories. |
| `edit_file` | `path`, `old_string`, `new_string`, `replace_all=false` | See 8.4. |
| `move_path` | `src`, `dst` | Both inside the workspace. Ask when moving more than a few files or across top-level directories. |
| `delete_path` | `path`, `recursive=false` | Always Ask. |
| `run_command` | `argv: list[str]`, `cwd?`, `timeout_s=120`, `env?` | No shell. See 8.5. |
| `bash` | `command`, `timeout_s=120` | Shell string, classified by the permission engine. See 8.5. |
| `git_status`, `git_diff`, `git_log`, `git_show` | typed args | Read-only. Allow. |
| `run_tests` | `target?` | Runs the configured or detected test command, optionally narrowed. |
| `run_verification` | `scope?` | Runs the verification pipeline (8.11). |
| `update_plan` | `items: [{text, status}]` | Persists plan rows. The plan is injected into context every turn. |
| `ask_user` | `question` | Blocks for a typed answer. Disabled in non-interactive mode. |
| `web_fetch` | `url` | Ask unless the domain is allowlisted. Output is untrusted. |
| `search_symbol`, `find_references` | typed args | Added only if the gate in section 9 passes. |

Tool descriptions given to the model must say what the tool does, when to use it, **when not to use it** (for example, `bash`: "do not use for reading files or searching; use read_file and grep"), side effects, argument meaning, and result meaning.

### 8.4 Editing rules

1. `edit_file` fails if `old_string` is absent, or is not unique while `replace_all` is false. The error reports the match count and line numbers.
2. The file must have been read earlier in the run. Hashes of what was read are stored (`files_read`). If the file changed on disk since, the edit fails with "file changed, re-read".
3. Before and after each edit, the content hash is recorded. After each edit the changed file is parse-checked where a parser is available (Python `ast`, others via configured syntax check) and the result is returned to the model.
4. Every edit is recorded as a diff and emits a `file.changed` event.
5. The agent must inspect `git_diff` before declaring a task complete.
6. Whole-file replacement is not offered for existing files. If an edit is objectively unsafe to express as a replacement, the model uses `write_file` to a new path plus `move_path`, which is subject to approval.

### 8.5 Command execution

- `run_command` takes `argv: list[str]`. No shell, no interpolation, no glob expansion. Runs in the workspace root (or sandbox). Timeout kills the whole process group. Output is combined, capped, tail-preserving.
- `bash` runs `/bin/bash -lc "<command>"` in the same conditions and is classified per 8.6. Both tools record command, cwd, start and end time, exit code, truncation, and timeout.
- Environment: the child process receives a filtered environment. API keys for model providers are never passed to commands.

### 8.6 Permission engine

A pure function: `decide(call, args, run) -> Allow | Ask(reason) | Deny(reason)`. No I/O except path resolution. Fully covered by table-driven tests.

**Risk levels** (each tool and each classified command maps to one):

| Level | Default |
|---|---|
| `READ_ONLY` | Allow |
| `LOCAL_MUTATION` (create or edit inside the workspace) | Allow (isolation and checkpoints exist). Config `edit_mode = "ask"` flips to Ask. |
| `EXTERNAL_SIDE_EFFECT` (network, installs) | Ask |
| `DESTRUCTIVE` (delete, reset, clean) | Ask |
| `FORBIDDEN` | Deny |

**Path rules (all file tools and redirections)**

1. Resolve with `realpath`. The result must be inside the workspace, otherwise Deny. Symlinks that escape are blocked.
2. Writes to `.git/` and to the agent's own state directory are Denied.
3. Secret-looking files (`.env*`, `*.pem`, `id_rsa*`, `*credentials*`, plus configured paths) are Ask to read and Deny to write.

**Shell classification (`bash`)**

1. Parse with `shlex`. Command substitution (`$(`, backticks), process substitution, heredocs, `eval`, or any parse failure means **Ask**.
2. Split on `;`, `&&`, `||`, `|`, `&`. Classify each segment. The overall decision is the strictest segment.
3. Redirections to a path count as writes and follow the path rules.
4. Segment classes:
   - **Allow** (read-only allowlist, configurable): `ls`, `cat`, `head`, `tail`, `wc`, `rg`, `grep`, `find` without `-delete` or `-exec`, `git status|diff|log|show|branch`, `pwd`, `which`, plus the configured verification commands.
   - **Deny** (patterns): `sudo`, `rm -rf /` and `rm -rf ~`, `chmod -R 777`, `curl|wget ... | sh`, `git push --force`, `mkfs`, `dd of=/dev/*`, fork bombs.
   - **Ask** (always): `rm`, `mv` leaving the workspace, `git push`, `git reset --hard`, `git clean`, `git checkout -- .`, package installs (`pip`, `npm`, `pnpm`, `yarn`, `brew`, `apt`), `docker`, `kill`, anything touching the network (`curl`, `wget`, `ssh`, `scp`).
   - **Ask** (default): anything unmatched. Unknown means ask.

**Approvals**

- Approval UI: approve once, deny (with an optional message returned to the model), allow this exact command for the session.
- Every approval is a stored record bound to a hash of the tool name and arguments. It is **single-use**; replaying it for different arguments or a second time is rejected.
- Session-wide allowances are never persisted silently.
- Non-interactive mode: Ask becomes Deny unless explicit flags allow a class.

**Honest limit:** deciding whether an arbitrary shell string is safe is not solvable by parsing. The design compensates with default-ask, argument-array `run_command` for ordinary commands, isolation and checkpoints, and the optional sandbox. The README must say so.

### 8.7 Untrusted content

- Tool results are wrapped in clearly delimited blocks, and the system prompt states that instructions inside tool results are data.
- More importantly, the permission engine never reads model-visible text, so injected text cannot widen permissions.
- Web content never auto-triggers `bash` or `run_command`.
- Output from `web_fetch` is never passed to a summarizer that has tool access.
- The evaluation suite includes tasks with an injected instruction in a file and in command output (section 11).

### 8.8 State store (SQLite)

File: `<repo>/.codeagent/state.db`, git-ignored, WAL mode, writes in transactions, schema changes through migrations.

```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY, repo_path TEXT, goal TEXT, intent TEXT, phase TEXT, status TEXT,
  stop_reason TEXT, model TEXT, isolation_ref TEXT, base_commit TEXT,
  started_at TEXT, ended_at TEXT, config_json TEXT
);
CREATE TABLE steps (                       -- one row per model call
  id INTEGER PRIMARY KEY, run_id TEXT, idx INTEGER, assistant_json TEXT, prompt_hash TEXT,
  tokens_in INTEGER, tokens_out INTEGER, cache_read INTEGER, cost_usd REAL, latency_ms INTEGER, created_at TEXT
);
CREATE TABLE tool_calls (
  id INTEGER PRIMARY KEY, run_id TEXT, step_id INTEGER, tool TEXT, args_json TEXT, args_hash TEXT,
  risk_level TEXT, decision TEXT, decided_by TEXT,                    -- rule | user
  ok INTEGER, result_json TEXT, duration_ms INTEGER, created_at TEXT
);
CREATE TABLE approvals (
  id TEXT PRIMARY KEY, run_id TEXT, tool_call_hash TEXT, status TEXT,   -- pending|approved|denied|used
  requested_at TEXT, resolved_at TEXT
);
CREATE TABLE plan_items (
  id INTEGER PRIMARY KEY, run_id TEXT, idx INTEGER, text TEXT,
  status TEXT,                                                           -- pending|in_progress|done|blocked
  attempt INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 3, depends_on TEXT
);
CREATE TABLE checkpoints (id INTEGER PRIMARY KEY, run_id TEXT, git_ref TEXT, label TEXT, created_at TEXT);
CREATE TABLE files_read (run_id TEXT, path TEXT, content_hash TEXT, PRIMARY KEY (run_id, path));
CREATE TABLE verification_runs (
  id INTEGER PRIMARY KEY, run_id TEXT, check_name TEXT, status TEXT,    -- pass|fail|skipped|unavailable
  command_json TEXT, duration_ms INTEGER, evidence TEXT, created_at TEXT
);
CREATE TABLE events (id INTEGER PRIMARY KEY, run_id TEXT, trace_id TEXT, span_id TEXT, name TEXT, ts TEXT, payload_json TEXT);
```

Resume (`codeagent resume <run_id>`): rebuild history from `steps` and `tool_calls`, restore the plan, compare the working tree with the last checkpoint plus recorded edits (warn on external changes; stale `files_read` hashes force re-reads), then continue.

Terminology: this is **task state**. Conversation history is working memory. Do not conflate them in code or documents.

### 8.9 Context management

Assembly order (stable parts first, for caching, D9):

1. System prompt (`prompts/system.md`).
2. Tool definitions.
3. Repository instructions and user preferences (8.10), loaded once at run start.
4. Plan (rendered from `plan_items`, placed as a message near the end because it changes).
5. History.

Compaction runs when estimated input tokens exceed `compact_threshold` (default 60% of the model window; in the free-tier profile, the absolute `max_request_tokens` of 8.20):

1. **Prune.** Replace old tool results (all but the most recent N, default 6) with stubs such as `[output of read_file src/x.py elided; 412 lines; re-run if needed]`.
2. **Summarize.** If still over, summarize everything before the last K turns (default 8) with the cheap model into one message: goal, decisions, files touched, failing checks, open questions. Summarize at most twice per run. After that, stop with a handoff summary: goal, decisions made, current state, exact next step.
3. **Never drop or summarize away:** the original goal, user messages, the current plan, the most recent verification result, any unresolved failure, exact error text, and file paths with line ranges.

Compaction invalidates the cached history portion. That is accepted because the stable prefix still hits cache.

Retrieval-built context (sections 9.4 to 9.5) is used only if the gate passes. It adds hits as ordinary tool results, never inside the stable prefix.

### 8.10 Memory

Four categories, kept separate:

| Category | Contents | Where |
|---|---|---|
| Task state | Plan, step status, retries, tool history, changed files, verification, approvals | SQLite (8.8). Authoritative. |
| Working context | Files recently read, current errors, current test output | The context window, rebuildable from task state. |
| Repository knowledge | Build and test commands, conventions, project instructions | `<repo>/CODEAGENT.md` (also reads `AGENTS.md` if present). Loaded each run. Capped at about 4,000 tokens, with a warning if exceeded. |
| User preferences | Style, preferred libraries, approval defaults | `~/.codeagent/preferences.md`. Same loader. |

Episodic memory is deferred. A `remember` tool that appends to the instructions file, only with approval, may be added later.

### 8.11 Verification and completion

**Pipeline** (inferred from the repository and overridable in config). Order:

```
syntax/parse → targeted tests → typecheck → lint → affected tests → build → diff review → acceptance criteria
```

Not every repository supports every check, so unsupported checks are recorded explicitly:

```python
class VerificationCheck(BaseModel):
    name: str
    status: Literal["pass", "fail", "skipped", "unavailable"]
    command: list[str] | None
    duration_ms: int
    evidence: str            # output tail or reason
```

Detection reads `pyproject.toml`, `package.json`, `Makefile`, and similar files. Detected commands are shown to the user on first use and stored in the repository's agent config.

**Completion gate.** A run may complete when:

- no mandatory check failed;
- the user's acceptance criteria are addressed in the final answer;
- no unexplained newly failing test exists;
- changed files are known and the final diff is available.

If the model ends its turn with edits made since the last passing verification, the gate injects one message asking it to verify or explain why that does not apply. If it still ends without verifying, the run finishes as `completed_unverified` and the CLI says so plainly.

**Final response contract:** root cause (for debugging), changed files, verification performed and its result, and unresolved concerns.

### 8.12 Failure handling and replanning

Failures are classified:

```
TRANSIENT · ENVIRONMENT · TEST_FAILURE · PATCH_CONFLICT · MISSING_CONTEXT ·
INVALID_PLAN · POLICY_BLOCK · BUDGET_EXHAUSTED · UNRECOVERABLE
```

A tool failure is not a task failure. Replanning triggers:

- the same tool fails twice for the same reason;
- verification fails after an edit;
- an expected file or symbol is absent;
- the repository changed externally;
- a plan assumption is disproven;
- a dependency cannot be installed;
- a call is blocked by policy.

On a trigger the loop injects a "change approach" message with the classified failure. Per-plan-item attempts are counted. At `max_attempts` (default 3) it injects "stop and reconsider the approach" once, then stops with a summary and asks the user. The repeat detector (identical tool and arguments three times within six calls) injects a warning once and stops if it recurs. After three consecutive denials the run stops and asks what the user wants.

### 8.13 Budgets and termination

| Guard | Default |
|---|---|
| `max_iterations` (model calls) | 50 (free-tier profile: 30) |
| `max_tool_calls` | 150 |
| `max_total_tokens` | 1,000,000 (free-tier profile: 150,000) |
| `max_cost_usd` | 5.00 (disabled when every price is zero) |
| `max_runtime_minutes` | 30 (free-tier profile: 90, because pacing waits count) |
| `max_same_failure_repetitions` | 2 |
| Denial streak | 3 |
| Interrupt | First Ctrl-C finishes the current tool, saves state, and stops. Second stops immediately. |

On exhaustion: stop mutating actions, persist state, run cheap read-only status collection, and report work accomplished, the current failure, changed files, verification state, and a suggested continuation. Every stop records a `stop_reason`.

### 8.14 Isolation and checkpoints

- **Default: a dedicated git worktree** at `.codeagent/worktrees/<run_id>` on branch `codeagent/<run_id>`. The user's working tree is untouched.
- **Fallback: branch mode.** If worktrees are unavailable, check for uncommitted changes, ask the user to stash, commit, or proceed, record the baseline, and never destroy pre-existing changes.
- **Checkpoints.** Commit before the first edit and after each passing verification (`codeagent: checkpoint <label>`), recorded in `checkpoints`.
- **Rollback.** `codeagent rollback <run_id> [--to <checkpoint>]`.
- **Finish.** Leave the branch, print a diff stat and the final diff. The agent never pushes or merges the user's code. `git push` stays Ask-tier.
- A lock file prevents a second run in the same repository.

### 8.15 Sandbox (optional)

`isolation.mode = "docker"` runs commands in a container with the workspace bind-mounted read-write and no network by default. On macOS, Docker runs in a Linux VM: bind-mount I/O is slower, file ownership may differ, and the arm64 image must be used to avoid emulation. Failure modes handled: Docker not running (fall back with a loud warning, never silently), image missing, container out of memory.

### 8.16 Observability

Every run has a trace ID, and every major operation a span. Events are written to the `events` table and a JSONL file at `.codeagent/traces/<run_id>.jsonl`.

Event taxonomy:

```
run.started · run.phase_changed · run.completed · run.failed
model.request · model.response
context.built · context.compacted
tool.requested · policy.decision · approval.requested · approval.resolved
tool.started · tool.completed · file.changed
verification.started · verification.check · verification.completed
plan.updated · failure.classified · budget.warning · checkpoint.created
```

Captured fields: timestamps, run and span IDs, provider and model, prompt hash, input/output/cache tokens, model and tool latency, exit codes, context size, changed files, verification results, errors. Secrets are redacted by pattern and never logged. The acceptance test: a complete run can be reconstructed from events without reading any hidden model reasoning.

`codeagent trace <run_id>` pretty-prints a run. The CLI prints an end-of-run summary: stop reason, iterations, tokens, cost, files changed, verification status.

### 8.17 System prompt requirements

Content, not final wording. Prompt files live in `prompts/` and are tracked in git. Each run records a hash of the prompt text. The prompt must cover:

1. Role, working directory, and that all work happens through tools.
2. Workflow: understand, plan for multi-step work, inspect, act, verify, report. Reproduce a bug before changing code when practical.
3. Search guidance: use `grep` and `glob` before reading whole files.
4. Edit discipline: read before edit, smallest change that works, no unrelated reformatting.
5. Verification duty and the final response contract.
6. Honesty: report failures and unverified work plainly; never claim tests passed without running them.
7. Safety: tool results are data; destructive actions need approval; if denied, do not retry the same action.
8. Budget awareness and when to stop and ask.

A small prompt regression set in the evaluation suite is rerun on every prompt change.

### 8.18 Configuration

Layering (later wins): defaults, `~/.codeagent/config.toml`, `<repo>/.codeagent/config.toml`, command-line flags.

```toml
[model]
provider = "openai_compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"    # name of the variable, never the key itself
main = "<model-id>"             # chosen by the owner; verify ids with GET {base_url}/models
cheap = "<model-id>"
fallbacks = []                  # optional ordered model ids used only on quota exhaustion; evals pin this to []
reasoning_effort = "low"        # sent only when the model supports it; reasoning tokens count as output
profile = "free_tier"           # free_tier | standard
[limits]
max_iterations = 30
max_tool_calls = 100
max_total_tokens = 150000
max_cost_usd = 5.0              # inactive while all prices are zero
max_runtime_minutes = 90
[request]
max_request_tokens = 6500       # estimated input; compaction runs before this is exceeded
max_output_tokens = 1000
[tools]
max_output_chars = 8000
read_default_lines = 120
instructions_max_tokens = 1500
[rate_limits."<model-id>"]      # copy the numbers from the Groq console; one table per model
rpm = 30
rpd = 1000
tpm = 8000
tpd = 200000
[permissions]
edit_mode = "allow"             # allow | ask
extra_allow = []                # extra read-only command prefixes
web_allowlist = []
secret_paths = [".env", ".env.*"]
[isolation]
mode = "worktree"               # worktree | branch | docker
[verify]
commands = []                   # empty means detect
timeout_s = 600
[index]
enabled = false
[prices]                        # per million tokens, optional; zero on the free tier
"<model-id>" = { input = 0.0, output = 0.0, cache_read = 0.0 }
```

`.env` loading: the API key is read from the process environment first, then from `.env` in the git root of the directory where `codeagent` was started, then from `~/.codeagent/.env`. The loader runs before any worktree is created, parses `KEY=value` lines only, never logs or echoes a value, and never passes the key to child processes. `.env.example` in the repository holds the variable name with a placeholder.

### 8.19 CLI

```
codeagent init                  # detect verification commands, write repo config
codeagent ask "<question>"      # read-only tools only
codeagent run "<goal>"
codeagent resume <run_id>
codeagent status <run_id>
codeagent rollback <run_id> [--to <checkpoint>]
codeagent trace <run_id>
codeagent config
```

Approval prompt shows the action, arguments, reason, risk level, and the choices: approve once, deny, allow this command for the session.


### 8.20 Free-tier operation (Groq)

The agent is developed, tested, and evaluated against Groq's free tier. The limits below are what the owner's Groq console showed for the models in use; they are configuration (`[rate_limits]`), not code, and must be rechecked in the console because Groq changes them.

| Model (free tier) | Requests/min | Requests/day | Tokens/min | Tokens/day |
|---|---:|---:|---:|---:|
| gpt-oss-120b, gpt-oss-20b, qwen model (each has its own quota) | 30 | 1,000 | 8,000 | 200,000 |

Input and output tokens both count. Cached input tokens do not. Arithmetic that shapes everything below: 200,000 tokens per day is only 25 calls of 8,000 tokens, and 8,000 tokens per minute means one full-size request per minute.

**Provider.** `OpenAICompatibleProvider(base_url, api_key_env)` uses Chat Completions with streaming and native tool calling (tool use, including parallel calls, is supported by the gpt-oss and qwen models). Unsupported request fields are never sent: `logprobs`, `logit_bias`, `top_logprobs`, `messages[].name`, and `n` other than 1.

**Free-tier profile (the default).** A small-context agent by design:

- System prompt plus tool definitions at most 3,000 estimated tokens; a test enforces it. Tool descriptions are terse.
- `max_request_tokens` 6,500 and `max_output_tokens` 1,000, so one call fits inside one minute's token allowance with margin. If assembly exceeds the cap, compact; if still over, stop with a handoff summary.
- Tool output capped at 8,000 characters, `read_file` defaults to 120 lines, repository instructions capped at 1,500 tokens.
- Compaction triggers on the absolute `max_request_tokens`, not on a percentage of the model window.
- `max_total_tokens` 150,000 per run: one run uses most of a model's daily quota. Warn before starting when the estimated need exceeds half of the remaining daily quota.
- Consequence to state plainly: this agent works well on small repositories and focused tasks. It is not expected to match larger-context models on large codebases. Evaluation fixtures are kept small for the same reason (11.3).

**Pacing and limits.**

1. A client-side token bucket per model for requests and tokens, charged with the estimated input plus `max_output_tokens` before a call and reconciled with the real `usage` after it.
2. On HTTP 429, wait for `retry-after` (plus jitter) when it is at most `max_wait_s` (default 120). Read `x-ratelimit-*` headers on every response and keep the last observed remaining and reset values per model in a `quota_state` table.
3. When the daily token or request allowance is exhausted, or `retry-after` exceeds `max_wait_s`: persist state, set the run to `WAITING_QUOTA`, print the reset time taken from the headers (never assume midnight), and exit cleanly. `codeagent resume <run_id>` continues from the saved state.
4. If `fallbacks` is set, switch to the next model only when the current one is quota-exhausted, and record the switch in the `model.request` event. Evaluation runs use no fallbacks.
5. It is not known what Groq does when a single request is larger than the per-minute token limit. The request cap in the profile avoids the case; the provider treats a "request too large" response as a non-retryable `context_overflow`.

**Cost.** Prices may all be zero. The cost guard is inactive in that case and token guards are the primary limit. The CLI shows tokens used and the estimated share of the daily quota.

**Tests.** No network. Header parsing and 429 handling use recorded fixtures; the limiter uses an injected clock so no test sleeps for real. Live tests are marked `live`, limited to a few short calls each, prefer the smaller model, and run only when the key exists.

---

## 9. Repository intelligence (gated)

Not built until the evaluation baseline justifies it.

### 9.1 Gate

Build this section only if the baseline report (BUILD_PLAN phase 8) shows either of:

- more than 30% of model calls in failed or over-budget tasks are search and file-reading calls; or
- tasks fail because the agent missed relevant code that a symbol or reference lookup would have found.

Each step below must then improve evaluation metrics (success rate, calls, tokens, or cost) or be removed.

### 9.2 Scanner

Resolve the repository root, load `.gitignore`, apply configurable default ignores (`.git/`, `node_modules/`, `.venv/`, `dist/`, `build/`, `coverage/`, `target/`, `__pycache__/`, minified files, binaries, large generated files), detect languages, hash files with SHA-256, and store a manifest. Start with Python and TypeScript.

### 9.3 Symbols and relationships

```python
class Symbol(BaseModel):
    symbol_id: str; file_path: str; language: str; kind: str; name: str
    qualified_name: str | None; signature: str | None
    start_line: int; end_line: int; parent_symbol_id: str | None; content_hash: str
```

Parse with tree-sitter so chunks respect function and class boundaries. Relations are stored in an SQLite edge table (`source_symbol_id`, `target_symbol_id`, `relation`, `confidence`): `CONTAINS`, `IMPORTS`, `CALLS`, `REFERENCES`, `INHERITS`, `IMPLEMENTS`, `TESTS`. Tree-sitter relations are approximate and carry a confidence. If exact language-server information becomes available it is preferred.

### 9.4 Retrieval

Order: exact text and regex, filename and path match, symbol-name match, structural relationships, neighboring code expansion, and only later optional semantic retrieval. Lexical ranking uses SQLite FTS5 with BM25.

```python
class RetrievalRequest(BaseModel):
    query: str; exact_terms: list[str] = []; symbol_terms: list[str] = []
    file_globs: list[str] = []; include_tests: bool = True; max_results: int = 30

class RetrievalHit(BaseModel):
    source: Literal["lexical", "symbol", "relationship", "semantic"]
    file_path: str; symbol_id: str | None; start_line: int; end_line: int
    score: float; reason: str          # every hit explains why it was selected
```

### 9.5 Expansion and compression

For a relevant function, expansion may include the containing class or module, direct callers and callees, imported types, implementations, adjacent error handling, tests targeting the symbol, and referenced configuration. Default depth is 1; deeper expansion needs a documented justification because it explodes. Expanded results are deduplicated, reranked deterministically, trimmed to a token budget, and summarized only when necessary. Source is preferred over summaries when it fits.

### 9.6 Freshness

```
filesystem event → normalize path → debounce (default 5 s of quiet) → SHA-256 →
compare with indexed hash → reparse changed file → replace that file's symbol and edge records →
bump index revision
```

On startup, scan the manifest, hash only what is needed, detect added, deleted, and changed files, and repair the index before the agent relies on it. Index updates are transactional. The agent's own edits emit change events so the index updates after each edit.

### 9.7 Ablation

Benchmark before keeping anything:

```
A: grep and glob only (the baseline)
B: A + symbol search
C: B + relationships and find_references
D: C + semantic retrieval (embeddings behind an interface)
```

Compare success rate, retrieval recall where ground truth exists, tokens, latency, and cost. Keep a step only if it produces a measurable gain. Recording a rejected experiment is a valid outcome.

---

## 10. Edge cases and failure modes

| Case | Handling |
|---|---|
| Malformed tool arguments | Tool error describing the schema problem. Counts toward the repeat detector. Never executes. |
| Unknown tool | Tool error listing available tools. |
| Huge file or minified blob | `read_file` refuses beyond a size cap and says so. The model uses `grep` or ranges. |
| Ambiguous `edit_file` match | Error with match count and line numbers. |
| File changed since it was read | Hash check fails the edit with "file changed, re-read". |
| User edits files during a run | Hash check; warning in the CLI. Worktree isolation makes this rare. |
| Command hangs | Timeout kills the process group. Result says timed out and shows the tail. |
| Enormous command output | Capped, tail kept. |
| Symlink escaping the workspace | Blocked by the `realpath` check. |
| Approval replay | Rejected; approvals are single-use and bound to argument hashes. |
| Model API outage mid-run | Retries, then stop with resumable state. |
| Context overflow after compaction | Stop and produce a handoff summary. |
| Fix introduces a new failure | Verification catches it. Attempt counter, reconsider message, rollback available. |
| Flaky test | Re-run a failed test once. If results differ, record it as flaky in the evidence and tell the user. Do not "fix" it blindly. |
| Docker not running | Loud warning; fall back only if the user allowed it. |
| Dirty working tree at start | Worktree mode does not touch it. Branch mode asks first. |
| **Out of scope for the initial release** | Multi-repo changes, binary file edits, Windows, concurrent runs in one repository. |

---

## 11. Evaluation

Without evaluation you cannot tell whether a change helped.

### 11.1 Layers

- **Unit and integration tests:** scripted `FakeProvider` transcripts exercise the loop, guards, permission decisions, resume, compaction, and failure handling.
- **Security tests** (`tests/security/`) must prove:
  1. `sudo` cannot execute;
  2. force-push is denied by default;
  3. deletion requires approval;
  4. configured secret paths cannot be read;
  5. a command timeout works;
  6. output truncation works;
  7. path traversal and escaping symlinks are blocked;
  8. existing user modifications are not silently overwritten;
  9. an approval cannot be reused;
  10. malformed model tool arguments cannot reach execution;
  11. an instruction injected in a file or command output does not change permissions;
  12. no tool runs before its policy decision is recorded.
- **Task suite** (`evals/tasks/`): 40 tasks, each a small fixture repository (at most about 15 files, none over 150 lines, so the free-tier context fits) plus `task.yaml` (`goal`, `check` command that must pass, optional limits, and a `reference_transcript` that scripts a correct solution for replay).

| Category | Count |
|---|---:|
| Repository navigation | 5 |
| Exact error localization | 5 |
| Single-file debugging | 5 |
| Multi-file debugging | 5 |
| Small feature | 5 |
| Multi-file feature | 5 |
| Test repair | 4 |
| Safe refusal and approval | 3 |
| Loop and failure handling (including injection and flaky tests) | 3 |

### 11.2 Metrics per run

Pass or fail by the check command, regressions, files changed and unnecessary files changed, iterations, tool calls, model calls, input, output and cache tokens, cost, wall time, policy violations, approval correctness, and (when the index exists) retrieval precision and recall.

### 11.3 Method

Two tiers, because the free tier cannot pay for repeated live runs of 40 tasks.

- **Tier 1: scripted replay (zero tokens, runs in CI).** Each task's `reference_transcript` drives `FakeProvider` through the real loop, tools, permissions, verification, and check command. It proves the harness, the fixtures, and the loop mechanics. It says nothing about model quality.
- **Tier 2: live slices (quota-aware).** `codeagent eval --live --slice core12 --resume` runs a 12-task core slice (two tasks each from navigation, localization, single-file debugging, multi-file debugging, small feature, and test repair) with one pinned model, no fallbacks, and a per-task token cap. It stops cleanly when the daily quota is reached and resumes on a later day. At about 100,000 tokens per task, the slice needs roughly six days of one model's free quota.
- **Free-tier baseline:** the core slice, one run per task. With 12 tasks and one run each the pass rate is indicative only and the report must say so. Repeat runs (three or more per task) and the full 40-task live run happen when quota or a paid tier allows.
- Primary measure: percentage of tasks completed correctly with all mandatory verification passing. Do not optimize token use at the expense of correctness until the success rate is stable.
- Rerun Tier 1 on every change. Rerun Tier 2 on changes to the prompt, loop, context, or permission logic as quota allows, and record which tasks were rerun.
- A sampled subset of a public benchmark such as SWE-bench may be added later. Check the current setup and licensing first.

---

## 12. Definition of done and demonstration

### 12.1 The initial release is done when

- the CLI works for `init`, `ask`, `run`, `resume`, `status`, `rollback`, `trace`;
- task state survives restarts and resume reaches the same state;
- the model uses tools iteratively through the native tool-calling loop;
- every tool call has a recorded policy decision before execution;
- destructive actions require single-use approval;
- worktree isolation, checkpoints, and rollback work;
- verification feeds the loop and the completion gate is enforced;
- all loops are bounded by the guards in 8.13;
- traces reconstruct any run;
- all 40 tasks run in scripted replay with one command, the core live slice runs with one command and resumes across days, and a baseline report (complete or explicitly partial) is committed;
- the demonstration below passes;
- all security tests pass.

Repository intelligence (section 9) is not required for the initial release. Its inclusion depends on the gate.

### 12.2 Demonstration scenario

Fixture: `examples/payment_service/`. An expired payment card raises an unhandled exception, the API returns HTTP 500 instead of 402, and a test fails.

```
codeagent run "Expired cards return HTTP 500 during checkout. Find the cause and fix it. Do not change unrelated behavior."
```

Expected autonomous sequence:

```
grep error and payment terms → locate checkout handler → locate payment service →
locate tests → run the targeted test → read the traceback → make the smallest edit →
run the targeted test → run affected tests → lint and typecheck → inspect the diff → final response
```

The final response states the root cause, changed files, verification performed, final test result, and unresolved concerns. This is the canonical end-to-end check.

---

## 13. Open questions

| # | Question | Resolution plan |
|---|---|---|
| 1 | Is `edit_mode = "allow"` the right default? | Decide when the permission phase is reviewed; the flag already exists. |
| 2 | Shell safety cannot be proven by parsing. | Default-ask, `run_command` for ordinary use, isolation, optional sandbox, documented limits. |
| 3 | Provider streaming details differ. | Contract tests against recorded fixtures per provider. |
| 4 | Summarization quality in long runs. | Prefer pruning over summarizing. Add long-horizon evaluation tasks. |
| 5 | Prompt wording sensitivity. | Prompt files tracked in git, run hash recorded, regression set rerun on change. |
| 6 | Quota exhaustion on the free tier. | Free-tier profile, client-side pacing, `WAITING_QUOTA` with resume, token guards primary (8.20). |
| 7 | Free-tier context is too small for large repositories. | Small-repository scope stated; fixtures kept small; revisit if a larger-context tier is adopted. |
| 8 | Groq limits, model ids, or supported parameters change. | Limits and ids are configuration; verify against the console and `GET /models` in the live smoke test. |
| 7 | Whether an index is needed at all. | The gate in section 9.1 decides, using measured data. |
