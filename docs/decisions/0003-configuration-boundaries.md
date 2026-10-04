# Configuration boundaries

## Context

P0-F4 requires Pydantic settings, layered TOML, and a limited KEY=value loader.
DESIGN 8.18 does not specify unset model IDs, populated verification commands,
or API-key representation. Profile application belongs to P6-F4.

## Decision

Use strict Pydantic v2 models, forbid extra keys, and recursively merge tables;
scalars and arrays replace earlier values. Unselected models are None and rate
and price tables are empty: there are no default model IDs or guessed prices.
All explicitly supplied prices require their three fields. The initial defaults
are the documented free-tier values; profile-specific application stays in P6-F4.
Verification commands are argument arrays, matching DESIGN 8.11's command type.

Use standard-library TOML and KEY=value parsing; no python-dotenv dependency is
needed. KEY=value supports blank/comment lines and matching outer quotes, without
expansion, export statements, multiline values, or inline-comment processing.
The first nonempty matching key wins within a file; empty values fall through.
Return SecretStr separately from settings and never modify the environment.
Discover the launch git root by walking to a .git file or directory, without a
subprocess that could inherit credentials. Callers load the key before isolation;
command-environment filtering remains P4-F1's responsibility.

## Consequences

Settings can be inspected without loading credentials. Validation errors omit
input values. Tests inject temporary user/repository paths and a synthetic
environment. Pydantic is the only dependency added, as prescribed by DESIGN 5.
