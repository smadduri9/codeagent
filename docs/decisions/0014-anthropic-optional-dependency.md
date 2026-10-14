# 0014: Anthropic SDK is an optional extra

## Context

The plan adds a native Anthropic provider (E1). It needs the official
`anthropic` Python SDK for HTTP and streaming. The OpenAI-compatible provider
already covers Groq, so the SDK is needed only when a user picks the Anthropic
provider.

## Decision

Add an optional extra, `anthropic = ["anthropic>=0.40"]`, in `pyproject.toml`.
The core install and the `dev` extra do not include it. The request and stream
mapping lives in `src/codeagent/providers/anthropic_mapping.py` and imports no
SDK, so its tests run without the extra.

## Consequences

- CI does not install the SDK, so the mapping tests cannot depend on it.
- E1c imports the SDK lazily and fails with a clear message when the extra is
  missing.
- Adding the SDK to `dev` would make every contributor install it; not chosen.
