# 0015: Price table includes a required cache-write price

## Context

`compute_cost` in `src/codeagent/providers/cost.py` priced input, output and
cache-read tokens. `Usage.cache_write` existed but was never billed, so cost
was understated for providers that charge a premium to write the prompt cache.

Existing test `tests/unit/test_config.py::test_missing_files_use_documented_defaults`
requires every `Price` field to be required, so no price is ever invented for an
unconfigured model.

## Decision

Add `cache_write` to `Price` as a required `Nonnegative` field, and bill
`usage.cache_write * price.cache_write` in `compute_cost`. No value is defined
in code.

Making the field required keeps that rule. Two existing fixtures build a
`Price` without it and gain `cache_write=0.0`: `tests/unit/test_budget_guards.py`
and the TOML in `tests/unit/test_config.py`. Those assertions are unchanged.

Public interface change: any user price table must now set `cache_write`.

## Consequences

- Tests: `tests/unit/test_cost.py` checks a 1M-token cache write at 1.25 per
  million costs 1.25.
- A user config without `cache_write` fails validation at load time. This is
  intentional; the error names the missing field.
- Follow-up: document the field in the config reference in `DESIGN.md` 8.18
  (owner-owned; decision needed).
