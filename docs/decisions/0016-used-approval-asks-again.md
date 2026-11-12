# 0016: A used approval asks again instead of denying

## Context

`DESIGN.md` 8.6 says an approval is single-use and that replaying it "a second
time is rejected". `resolve_ask` implemented that by returning
`Deny("approval already used")` for every later call with the same tool name and
arguments, without consulting the operator.

In practice the agent repeats identical commands on purpose. Approving
`pytest -q` once meant the second test run in the same session was refused
silently, with no way for the operator to allow it short of a session-wide
allowance.

## Decision

Keep approvals single-use, and change what happens after one is used: an
identical later call is treated as a new request and the operator is prompted
again. `ApprovalStore.consume` is unchanged and still rejects replay of a spent
record, so one answer never authorizes two executions.

The security property is unchanged: no Ask-tier call executes without an
explicit answer given for that call, or a session allowance the operator chose.
Non-interactive mode is unchanged: Ask still becomes Deny.

No public signature changes. Reference: fix round 1, FIX-05.

## Consequences

- Two existing tests asserted the old behaviour by answering "once" twice and
  expecting a denial: `tests/unit/test_permissions_approvals.py::test_single_use_approval_rejects_replay`
  and `tests/security/test_approvals_and_loop.py::test_approval_cannot_be_reused`.
  They now assert the property directly: after a used approval, a refusal is
  honoured and the spent record cannot be consumed again.
- New tests in `tests/security/test_approval_reask.py` check that the prompt is
  consulted for every identical call, that a once-approval never becomes a
  session allowance, and that a session allowance still suppresses the prompt.
- The operator sees more prompts for repeated commands. "Allow for session"
  remains the way to stop them for one exact command.
- Follow-up: `DESIGN.md` 8.6 wording ("a second time is rejected") should be
  clarified by the owner (owner-owned file).
