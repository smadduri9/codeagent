"""Schema migrations for the state database."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  repo_path TEXT NOT NULL,
  goal TEXT NOT NULL,
  intent TEXT,
  phase TEXT NOT NULL,
  status TEXT NOT NULL,
  stop_reason TEXT,
  model TEXT,
  isolation_ref TEXT,
  base_commit TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  config_json TEXT
);

CREATE TABLE IF NOT EXISTS steps (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  assistant_json TEXT NOT NULL,
  prompt_hash TEXT,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  cache_read INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  latency_ms INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id INTEGER NOT NULL,
  tool TEXT NOT NULL,
  args_json TEXT NOT NULL,
  args_hash TEXT,
  risk_level TEXT,
  decision TEXT NOT NULL,
  decided_by TEXT,
  ok INTEGER,
  result_json TEXT,
  duration_ms INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(id),
  FOREIGN KEY (step_id) REFERENCES steps(id)
);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  tool_call_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  resolved_at TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS plan_items (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  depends_on TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  git_ref TEXT NOT NULL,
  label TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS files_read (
  run_id TEXT NOT NULL,
  path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, path),
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS verification_runs (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  check_name TEXT NOT NULL,
  status TEXT NOT NULL,
  command_json TEXT,
  duration_ms INTEGER,
  evidence TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  trace_id TEXT,
  span_id TEXT,
  name TEXT NOT NULL,
  ts TEXT NOT NULL,
  payload_json TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id, idx);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id, step_id);
"""

MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS quota_state (
  model TEXT PRIMARY KEY,
  requests_remaining INTEGER,
  tokens_remaining INTEGER,
  reset_at TEXT,
  updated_at TEXT NOT NULL
);
"""

MIGRATIONS: Sequence[tuple[int, str]] = (
    (1, MIGRATION_1),
    (2, MIGRATION_2),
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def current_schema_version(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """,
    )
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Apply pending migrations; return the schema version after applying."""
    applied = 0
    version = current_schema_version(connection)
    for migration_version, sql in MIGRATIONS:
        if migration_version <= version:
            continue
        connection.executescript(sql)
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (migration_version, _utc_now()),
        )
        applied += 1
        version = migration_version
    return version if applied == 0 else current_schema_version(connection)
