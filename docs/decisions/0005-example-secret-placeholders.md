# Restrict example-file exemptions to exact placeholders

## Context

The medium finding in `phase-0-review-1-20261004-131051.md` shows that
P0-F2's scanner exempts all credential assignments in any `.env.example`.
BUILD_PLAN section 4 requires detecting credential content in tracked files;
DESIGN 8.18 permits a placeholder in the owner-supplied example.

## Decision

Accept the finding. Exempt only the complete values `your_groq_key_here`
(the owner-supplied template) and `your-key-here` (the existing regression
fixture), optionally enclosed in matching quotes. Apply the exemption only
to `.env.example` files, including nested examples. Other assignments retain
the existing detection patterns. Provider-key and private-key patterns inspect
the entire original content, with no placeholder exemptions.

## Consequences

Both staged and working-tree copies are scanned independently. Mixed example
and credential lines fail; prefixes, suffixes, trailing text, and mismatched
quotes cannot turn a value into an allowed placeholder. Diagnostics continue
to withhold content. Tests use temporary repositories and synthetic values.
No dependency or public product interface changes, and no owner-owned file
changes. Pattern scanning remains heuristic; this fix does not broaden the
existing credential-name patterns or eight-character assignment threshold.
