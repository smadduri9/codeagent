# 0019: A git-tracked repository config may not set sensitive keys

## Context

`DESIGN.md` 8.18 layers `<repo>/.codeagent/config.toml` over the user's config.
That file can set `model.base_url` and `model.api_key_env`, so a cloned
repository that ships it could send the operator's API key (or any environment
variable it names) to its own endpoint. It can also set `[verify]` commands,
which the agent runs, and `[permissions]`.

`DESIGN.md` 8.11 also says detected verification commands are stored in the
repository's agent config, and `codeagent init` and `chat` write `[verify]`
there. So those keys cannot simply be ignored at repository level.

## Decision

Trust the repository config by where it came from. A file git reports as
tracked arrived with the repository and is refused if it sets `model.base_url`,
`model.api_key_env`, any `[verify]` key, or any `[permissions]` key. Loading
fails with a `ConfigError` that names the keys (never the values) and says to
move them to `~/.codeagent/config.toml` or untrack the file. An untracked file
(the normal case: `.codeagent/` is git-ignored and written by `init`) is trusted
as before. Other keys, such as `model.main` and `[limits]`, stay allowed in a
tracked file.

The check runs `git ls-files --error-unmatch` with an environment reduced to
`PATH`, `HOME` and `LC_ALL`. This departs from decision 0003, which avoided any
subprocess in config loading so no child could inherit credentials; the reduced
environment keeps that property. If git is missing or the directory is not a
real repository the file is treated as untracked.

No public signature changes. Reference: fix round 1, FIX-13.

## Consequences

- Tests: `tests/security/test_config_trust.py`.
- A team that commits `.codeagent/config.toml` with verification commands must
  untrack it or move those keys to each user's home config.
- Not covered: a repository unpacked from an archive rather than cloned, where
  nothing is tracked. The README should say to read `.codeagent/config.toml`
  before running the agent in a directory obtained that way.
- Follow-up: `DESIGN.md` 8.18 should mention the rule (owner-owned file).
