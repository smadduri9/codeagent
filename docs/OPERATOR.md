# Operator guide

Step-by-step instructions for running CodeAgent on any GitHub repository with Groq.

## Prerequisites

- Python 3.12 and this package installed (`pip install -e .` from the CodeAgent repo).
- A Git checkout of the project you want the agent to work on.
- A Groq API key in the environment **or** in `.env` at the repository root (never commit it).
- Optional: Docker Desktop if you set `isolation.mode = "docker"` for sandboxed shell commands.

## One-time setup in your target repository

1. Clone the repository you want to edit:

   ```bash
   git clone https://github.com/org/your-project.git
   cd your-project
   ```

2. Create configuration (merge with defaults):

   ```bash
   mkdir -p .codeagent
   ```

   Edit `.codeagent/config.toml`:

   ```toml
   [model]
   main = "llama-3.3-70b-versatile"   # pin a Groq model id from your account

   [limits]
   max_iterations = 20
   ```

3. Put your API key where the loader expects it (pick one):

   - Export `GROQ_API_KEY` in your shell, **or**
   - Add `GROQ_API_KEY=...` to `.env` in the repository root (gitignored).

4. Optional: detect verification commands:

   ```bash
   codeagent init
   ```

## Run the agent

From the repository root:

```bash
codeagent run "Describe your task in plain language" --persist
```

- `--persist` saves the run to SQLite (`.codeagent/state.db`), creates a git worktree
  (or branch fallback), and prints a final diff when finished.
- The CLI prompts for **Ask**-tier tools (destructive shell, deletes, etc.). Use
  `y` once, `s` for the rest of the session, or `n` to deny.
- Use `-y` / `--yes` to auto-approve Ask-tier tools (CI or trusted runs only).

Scripted demos and tests still use the hidden flag:

```bash
codeagent run "goal" --fake-script path/to/script.json
```

## Resume after interrupt or quota stop

List runs:

```bash
codeagent status
```

Resume:

```bash
codeagent resume <run_id>
```

## Inspect a run

```bash
codeagent trace <run_id>
codeagent status <run_id>
```

## Roll back checkpoints

```bash
codeagent rollback <run_id>
```

## Evaluation (baseline)

From the CodeAgent source tree:

```bash
codeagent eval --slice core12 --live --resume
```

Stops when daily quota is exhausted; results land under `evals/baselines/`. (Requires the eval CLI from the live baseline PR.)

## Recommended first local command

After configuring `model.main` and your Groq key:

```bash
cd your-project
codeagent run "List the top-level files and summarize the project in three bullets" --persist
```

Use a small public Python repo and a short goal to stay within the free tier.
