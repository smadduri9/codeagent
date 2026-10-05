from codeagent.loop import RunResult
from codeagent.state.store import StateStore


def format_run_summary(store: StateStore, run_id: str, result: RunResult) -> str:
    tin, tout, cost = store.aggregate_usage(run_id)
    return (
        f"stop={result.stop_reason} iterations={result.iterations} "
        f"tokens={tin}+{tout} cost={cost:.4f}"
    )
