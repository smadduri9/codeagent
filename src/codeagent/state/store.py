"""Typed access layer for SQLite task state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codeagent.lifecycle import RunPhase
from codeagent.permissions.types import Allow, Ask, Decision
from codeagent.providers.base import Message, ToolCall
from codeagent.state.migrations import apply_migrations


@dataclass(frozen=True)
class QuotaSnapshot:
    model: str
    requests_remaining: int | None
    tokens_remaining: int | None
    reset_at: str | None


def default_state_db_path(repo_root: Path) -> Path:
    return repo_root / ".codeagent" / "state.db"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def args_hash_for_tool(args: dict[str, object]) -> str:
    return _args_hash(args)


def _args_hash(args: dict[str, object]) -> str:
    payload = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decision_fields(decision: Decision) -> tuple[str, str | None, str | None]:
    if isinstance(decision, Allow):
        return "allow", decision.decided_by, decision.risk_level.value
    if isinstance(decision, Ask):
        risk = decision.risk_level.value if decision.risk_level else None
        return "ask", None, risk
    risk = decision.risk_level.value if decision.risk_level else None
    return "deny", None, risk


@dataclass(frozen=True, slots=True)
class PlanItemRecord:
    idx: int
    text: str
    status: str
    depends_on: list[int]
    attempt: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: int
    run_id: str
    trace_id: str | None
    span_id: str | None
    name: str
    ts: str
    payload_json: str | None


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: str
    repo_path: str
    goal: str
    phase: str
    status: str
    stop_reason: str | None
    model: str | None
    started_at: str
    ended_at: str | None
    config_json: str | None


class StateStore:
    """SQLite store with WAL mode and transactional writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        apply_migrations(conn)
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> StateStore:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _transaction(self) -> sqlite3.Connection:
        conn = self.connect()
        conn.execute("BEGIN IMMEDIATE")
        return conn

    def upsert_quota(self, snapshot: QuotaSnapshot) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO quota_state (
                  model, requests_remaining, tokens_remaining, reset_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(model) DO UPDATE SET
                  requests_remaining=excluded.requests_remaining,
                  tokens_remaining=excluded.tokens_remaining,
                  reset_at=excluded.reset_at,
                  updated_at=excluded.updated_at
                """,
                (
                    snapshot.model,
                    snapshot.requests_remaining,
                    snapshot.tokens_remaining,
                    snapshot.reset_at,
                    _utc_now(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def get_quota(self, model: str) -> QuotaSnapshot | None:
        conn = self.connect()
        row = conn.execute(
            """
            SELECT model, requests_remaining, tokens_remaining, reset_at
            FROM quota_state WHERE model = ?
            """,
            (model,),
        ).fetchone()
        if row is None:
            return None
        return QuotaSnapshot(
            model=row["model"],
            requests_remaining=row["requests_remaining"],
            tokens_remaining=row["tokens_remaining"],
            reset_at=row["reset_at"],
        )

    def create_run(
        self,
        *,
        repo_path: Path,
        goal: str,
        model: str,
        config_json: str | None = None,
        run_id: str | None = None,
    ) -> str:
        rid = run_id or uuid.uuid4().hex
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO runs (
                  id, repo_path, goal, intent, phase, status, stop_reason, model,
                  isolation_ref, base_commit, started_at, ended_at, config_json
                ) VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, NULL, NULL, ?, NULL, ?)
                """,
                (
                    rid,
                    repo_path.as_posix(),
                    goal,
                    RunPhase.INITIALIZING.value,
                    "active",
                    model,
                    _utc_now(),
                    config_json,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return rid

    def update_run_phase(self, run_id: str, phase: RunPhase) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                "UPDATE runs SET phase = ? WHERE id = ?",
                (phase.value, run_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def finish_run(
        self,
        run_id: str,
        *,
        phase: RunPhase,
        stop_reason: str | None,
        status: str = "finished",
    ) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                """
                UPDATE runs SET phase = ?, status = ?, stop_reason = ?, ended_at = ?
                WHERE id = ?
                """,
                (phase.value, status, stop_reason, _utc_now(), run_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def get_run(self, run_id: str) -> RunRecord | None:
        conn = self.connect()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return RunRecord(
            id=row["id"],
            repo_path=row["repo_path"],
            goal=row["goal"],
            phase=row["phase"],
            status=row["status"],
            stop_reason=row["stop_reason"],
            model=row["model"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            config_json=row["config_json"],
        )

    def list_runs(self, limit: int = 20) -> list[RunRecord]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            RunRecord(
                id=row["id"],
                repo_path=row["repo_path"],
                goal=row["goal"],
                phase=row["phase"],
                status=row["status"],
                stop_reason=row["stop_reason"],
                model=row["model"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                config_json=row["config_json"],
            )
            for row in rows
        ]

    def next_step_index(self, run_id: str) -> int:
        conn = self.connect()
        row = conn.execute(
            "SELECT COALESCE(MAX(idx), -1) AS max_idx FROM steps WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return int(row["max_idx"]) + 1

    def insert_step(
        self,
        run_id: str,
        *,
        idx: int,
        assistant: Message,
        tokens_in: int,
        tokens_out: int,
        cache_read: int,
        cost_usd: float,
        latency_ms: int | None,
        prompt_hash: str | None = None,
    ) -> int:
        conn = self._transaction()
        try:
            cursor = conn.execute(
                """
                INSERT INTO steps (
                  run_id, idx, assistant_json, prompt_hash, tokens_in, tokens_out,
                  cache_read, cost_usd, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    idx,
                    assistant.model_dump_json(),
                    prompt_hash,
                    tokens_in,
                    tokens_out,
                    cache_read,
                    cost_usd,
                    latency_ms,
                    _utc_now(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("insert_step did not return a row id")
        return int(row_id)

    def list_steps(self, run_id: str) -> list[sqlite3.Row]:
        conn = self.connect()
        return list(
            conn.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY idx ASC",
                (run_id,),
            ).fetchall(),
        )

    def begin_tool_call(
        self,
        run_id: str,
        step_id: int,
        call: ToolCall,
        decision: Decision,
    ) -> int:
        decision_kind, decided_by, risk_level = _decision_fields(decision)
        conn = self._transaction()
        try:
            cursor = conn.execute(
                """
                INSERT INTO tool_calls (
                  run_id, step_id, tool, args_json, args_hash, risk_level, decision,
                  decided_by, ok, result_json, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
                """,
                (
                    run_id,
                    step_id,
                    call.name,
                    json.dumps(call.args, sort_keys=True),
                    _args_hash(call.args),
                    risk_level,
                    decision_kind,
                    decided_by,
                    _utc_now(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("begin_tool_call did not return a row id")
        return int(row_id)

    def complete_tool_call(
        self,
        tool_call_id: int,
        *,
        ok: bool,
        result_content: str,
        duration_ms: int,
    ) -> None:
        payload = json.dumps({"content": result_content})
        conn = self._transaction()
        try:
            conn.execute(
                """
                UPDATE tool_calls SET ok = ?, result_json = ?, duration_ms = ?
                WHERE id = ?
                """,
                (1 if ok else 0, payload, duration_ms, tool_call_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_tool_calls(self, run_id: str) -> list[sqlite3.Row]:
        conn = self.connect()
        return list(
            conn.execute(
                """
                SELECT * FROM tool_calls WHERE run_id = ?
                ORDER BY step_id ASC, id ASC
                """,
                (run_id,),
            ).fetchall(),
        )

    def record_file_read(self, run_id: str, path: Path, content_hash: str) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO files_read (run_id, path, content_hash) VALUES (?, ?, ?)
                ON CONFLICT(run_id, path) DO UPDATE SET content_hash = excluded.content_hash
                """,
                (run_id, path.as_posix(), content_hash),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_files_read(self, run_id: str) -> dict[str, str]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT path, content_hash FROM files_read WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        return {row["path"]: row["content_hash"] for row in rows}

    def replace_plan_items(
        self,
        run_id: str,
        items: list[PlanItemRecord],
    ) -> None:
        conn = self._transaction()
        try:
            conn.execute("DELETE FROM plan_items WHERE run_id = ?", (run_id,))
            for item in items:
                depends = json.dumps(item.depends_on)
                conn.execute(
                    """
                    INSERT INTO plan_items (
                      run_id, idx, text, status, attempt, max_attempts, depends_on
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item.idx,
                        item.text,
                        item.status,
                        item.attempt,
                        item.max_attempts,
                        depends,
                    ),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_plan_items(self, run_id: str) -> list[PlanItemRecord]:
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT idx, text, status, attempt, max_attempts, depends_on
            FROM plan_items WHERE run_id = ? ORDER BY idx ASC
            """,
            (run_id,),
        ).fetchall()
        items: list[PlanItemRecord] = []
        for row in rows:
            raw_deps = row["depends_on"]
            deps: list[int] = []
            if raw_deps:
                deps = [int(v) for v in json.loads(raw_deps)]
            items.append(
                PlanItemRecord(
                    idx=int(row["idx"]),
                    text=row["text"],
                    status=row["status"],
                    depends_on=deps,
                    attempt=int(row["attempt"]),
                    max_attempts=int(row["max_attempts"]),
                ),
            )
        return items

    def increment_plan_attempt(self, run_id: str, idx: int) -> int:
        conn = self._transaction()
        try:
            conn.execute(
                """
                UPDATE plan_items SET attempt = attempt + 1
                WHERE run_id = ? AND idx = ?
                """,
                (run_id, idx),
            )
            row = conn.execute(
                "SELECT attempt FROM plan_items WHERE run_id = ? AND idx = ?",
                (run_id, idx),
            ).fetchone()
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        if row is None:
            raise ValueError(f"unknown plan item: {idx}")
        return int(row["attempt"])

    def insert_verification_check(
        self,
        run_id: str,
        *,
        check_name: str,
        status: str,
        command: list[str] | None,
        duration_ms: int,
        evidence: str,
    ) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO verification_runs (
                  run_id, check_name, status, command_json, duration_ms, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    check_name,
                    status,
                    json.dumps(command) if command else None,
                    duration_ms,
                    evidence,
                    _utc_now(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_verification_checks(self, run_id: str) -> list[sqlite3.Row]:
        conn = self.connect()
        return list(
            conn.execute(
                """
                SELECT * FROM verification_runs WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall(),
        )

    def record_approval(
        self,
        run_id: str,
        approval_id: str,
        tool_call_hash: str,
        status: str,
        *,
        resolved: bool = False,
    ) -> None:
        now = _utc_now()
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO approvals (
                  id, run_id, tool_call_hash, status, requested_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    run_id,
                    tool_call_hash,
                    status,
                    now,
                    now if resolved else None,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_approvals(self, run_id: str) -> list[sqlite3.Row]:
        conn = self.connect()
        return list(
            conn.execute("SELECT * FROM approvals WHERE run_id = ?", (run_id,)).fetchall(),
        )

    def aggregate_usage(self, run_id: str) -> tuple[int, int, float]:
        conn = self.connect()
        row = conn.execute(
            """
            SELECT
              COALESCE(SUM(tokens_in), 0) AS tin,
              COALESCE(SUM(tokens_out), 0) AS tout,
              COALESCE(SUM(cost_usd), 0) AS cost
            FROM steps WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return int(row["tin"]), int(row["tout"]), float(row["cost"])

    def count_tool_calls(self, run_id: str) -> int:
        conn = self.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM tool_calls WHERE run_id = ? AND ok IS NOT NULL",
            (run_id,),
        ).fetchone()
        return int(row["c"])

    def record_event(
        self,
        run_id: str,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        conn = self._transaction()
        try:
            conn.execute(
                """
                INSERT INTO events (run_id, trace_id, span_id, name, ts, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    trace_id,
                    span_id,
                    name,
                    _utc_now(),
                    json.dumps(payload) if payload else None,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_events(self, run_id: str) -> list[StoredEvent]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [
            StoredEvent(
                id=int(row["id"]),
                run_id=row["run_id"],
                trace_id=row["trace_id"],
                span_id=row["span_id"],
                name=row["name"],
                ts=row["ts"],
                payload_json=row["payload_json"],
            )
            for row in rows
        ]
