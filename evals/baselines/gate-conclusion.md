# Repository intelligence gate (DESIGN 9.1)

## Replay baseline

The full scripted replay suite (40 evaluation tasks plus two harness smoke tasks)
completed with a 100% pass rate using reference transcripts. See
`evals/baselines/replay-40/report.md` and `results.json`.

## Live core12 baseline

No live Groq runs were executed in the automated build session (free-tier quota
preservation). Tasks completed: **0 / 12** in the `core12` slice.

## Conclusion

**Undetermined — repository intelligence stays off.**

Phase 9 must not start until a live `core12` baseline exists and can be read
against the DESIGN 9.1 gate. The owner may continue with:

`codeagent eval --live --slice core12 --resume`
