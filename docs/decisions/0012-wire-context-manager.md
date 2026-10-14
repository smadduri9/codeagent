# 0012: The agent loop uses ContextManager

## Context

`ContextManager` (`src/codeagent/context/manager.py`) builds the stable prompt
prefix and runs history compaction. Nothing in the application constructed it,
so real runs sent the full, growing history on every model call and never
compacted. The component was tested only in isolation.

## Decision

`run_agent_loop` takes an optional keyword `context: ContextManager | None`.
When it is given, each model request is built from `context.assemble(...)`: its
system prompt and messages replace the loop's `system` and `chat_history` for
that call. If compaction changed the history, `chat_history` is replaced with
the compacted version and a `context.compacted` event is emitted.

`run_with_persistence` passes the argument through. `cli_run.py` and
`cli_resume.py` build one with `build_context_manager` in
`runtime/bootstrap.py`. When `context` is None, behaviour is unchanged.

The system prompt is not doubled: `assemble` appends repository instructions in
the same format as `build_system_prompt`, so the `system` argument is ignored
when a context is given.

Public interface change: `run_agent_loop` and `run_with_persistence` gain one
optional keyword each.

## Consequences

- Tests: `tests/unit/test_loop_context.py` shows compaction shrinks the history
  sent to the model, and that without a context the full history is sent.
- Persisted history is not compacted. A resumed run rebuilds the full history
  and compacts again on its first request.
- Follow-up: W2 wires the failure classifier. Observability for context
  composition is O4.
