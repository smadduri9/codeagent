# CodeAgent

A local CLI coding agent, built according to [DESIGN.md](DESIGN.md) and
[BUILD_PLAN.md](BUILD_PLAN.md). Python 3.12+, Git, and ripgrep are required.
The primary platform is macOS arm64; Linux is also a target.

## Current status

P0-F1 provides the package, CLI help, and development checks. The agent loop,
provider, tools, and remaining CLI commands are planned, **not implemented yet**.
The application will use the owner's configured OpenAI-compatible endpoint
(Groq by default); no provider call or API key is needed for the bootstrap.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
codeagent --help
scripts/check.sh
```

If Python is managed by uv, use `uv venv --python 3.12 .venv` and
`uv pip install --python .venv/bin/python -e '.[dev]'` instead.

Checks run Ruff lint and formatting, strict mypy, and offline pytest tests.
Tests marked `live` are excluded. Never commit `.env`, API keys, run databases,
or build logs. The implementing agent must not open the owner's `.env` file.

Build one feature per branch and PR, following `AGENTS.md`. The existing
`scripts/autobuild.sh` is the owner-supplied **Cursor** driver. It is not a
Codex launcher. Initial release work ends at phase 8; repository indexing is
gated on evaluation evidence. A full live free-tier baseline can take days.

Shell command safety cannot be proven by parsing. The planned permission
engine uses default-ask rules, argument-array execution, isolation, and
optional sandboxing; these protections are not present in this bootstrap.
