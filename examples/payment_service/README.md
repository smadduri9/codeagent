# Payment service demonstration

Fixture for DESIGN 12.2: expired cards currently return HTTP 500 instead of 402.

## Scripted test

`tests/unit/test_payment_demo.py` runs a scripted sequence that maps the expired-card
exception to HTTP 402.

## Live demonstration

With a configured Groq key:

```bash
cd examples/payment_service
codeagent run "Expired cards return HTTP 500 during checkout. Find the cause and fix it. Do not change unrelated behavior."
```

Capture the resulting trace with `codeagent trace` and attach it to release notes when run.
