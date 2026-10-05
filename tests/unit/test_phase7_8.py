from pathlib import Path

import yaml

from codeagent.config import Settings
from codeagent.failures import AttemptLimiter, IdenticalRetryGuard
from codeagent.loop.completion_gate import CompletionGate, GateAction
from codeagent.observability.events import EVENT_NAMES, EventEmitter
from codeagent.observability.sink import DatabaseEventSink, JsonlEventSink
from codeagent.plan.render import order_plan_items
from codeagent.providers.base import ToolCall
from codeagent.state.store import PlanItemRecord, StateStore
from codeagent.tools.plan_tools import PlanItemInput, UpdatePlanArgs, handle_update_plan
from codeagent.tools.registry import ToolRegistry
from codeagent.verification.detect import detect_commands
from codeagent.verification.flaky import evaluate_flaky
from codeagent.verification.pipeline import CommandRunner, VerificationPipeline
from evals.runner import run_eval


def test_plan_and_resume(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "s.db")
    rid = store.create_run(repo_path=tmp_path, goal="g", model="m")
    handle_update_plan(
        UpdatePlanArgs(
            items=[
                PlanItemInput(text="first", status="in_progress"),
                PlanItemInput(text="second", status="pending", depends_on=[0]),
            ],
        ),
        store=store,
        run_id=rid,
    )
    ordered = order_plan_items(store.list_plan_items(rid))
    assert ordered[0].text == "first"
    store.close()


def test_detect_and_verify(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    assert detect_commands(tmp_path).test is not None
    settings = Settings()
    settings.verify.test = ["false"]

    class Fake(CommandRunner):
        def run(self, command: list[str], *, cwd: Path, timeout_s: int) -> tuple[int, str]:
            return 1, "fail"

    checks = VerificationPipeline(tmp_path, settings.verify, runner=Fake()).run(scope="test")
    assert checks[1].status == "fail"
    lint_checks = VerificationPipeline(tmp_path, settings.verify, runner=Fake()).run(scope="lint")
    assert lint_checks[1].status == "unavailable"


def test_gate_flaky_events_eval(tmp_path: Path) -> None:
    gate = CompletionGate()
    gate.note_edit()
    assert gate.on_model_stop() is GateAction.PROMPT_VERIFY
    assert evaluate_flaky(True, False).flaky
    store = StateStore(tmp_path / "s.db")
    rid = store.create_run(repo_path=tmp_path, goal="g", model="m")
    emitter = EventEmitter(rid, [DatabaseEventSink(store), JsonlEventSink(tmp_path / "t.jsonl")])
    for name in EVENT_NAMES:
        emitter.emit(name, {"k": "Bearer secret"})
    assert "REDACTED" in (tmp_path / "t.jsonl").read_text(encoding="utf-8")
    guard = IdenticalRetryGuard()
    call = ToolCall(id="1", name="grep", args={"pattern": "a"})
    assert guard.check(call) is None
    assert guard.check(call) is None
    assert guard.check(call) is not None
    store.replace_plan_items(
        rid,
        [
            PlanItemRecord(
                idx=0, text="t", status="in_progress", depends_on=[], attempt=2, max_attempts=3
            )
        ],
    )
    limiter = AttemptLimiter(store, rid)
    assert limiter.record_failure()
    assert limiter.record_failure()
    tasks = tmp_path / "tasks"
    for name in ("a", "b"):
        d = tasks / name
        d.mkdir(parents=True)
        (d / "task.yaml").write_text(
            yaml.dump(
                {
                    "id": name,
                    "check": {"command": ["python", "-c", "import sys; sys.exit(0)"]},
                    "reference_transcript": [{"x": 1}],
                },
            ),
            encoding="utf-8",
        )
    out = tmp_path / "out"
    assert len(run_eval(tasks_dir=tasks, output_dir=out, mode="replay").results) == 2
    assert (out / "results.json").exists()
    registry = ToolRegistry()
    registry.register_workflow_tools(
        store=store, run_id=rid, repo_root=tmp_path, settings=Settings(), edited_py_files=[]
    )
    assert registry.run(
        ToolCall(id="1", name="update_plan", args={"items": [{"text": "x", "status": "pending"}]})
    ).ok
    store.close()
