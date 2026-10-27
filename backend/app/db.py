"""Warehouse access. SQLite via SQLAlchemy so the same code can point at Postgres in deployment."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from .config import settings

_engine: Engine | None = None
_lock = threading.RLock()
_version = {"n": 0}

SCHEMA_VERSION = "2025.1"

APP_TABLES = """
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_type TEXT, unit TEXT, title TEXT, indicator TEXT, evidence TEXT,
    created_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER, title TEXT, description TEXT, intervention_key TEXT,
    unit_type TEXT, unit TEXT, schools TEXT,
    owner_name TEXT, owner_role TEXT, owner_id TEXT, due_date TEXT, priority TEXT,
    status TEXT, created_by TEXT, created_at TEXT,
    verified_by TEXT, verified_at TEXT, evidence_note TEXT, evidence_file TEXT,
    learning_indicator TEXT, implementation_indicator TEXT,
    is_simulated INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS action_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id INTEGER, user_name TEXT, note TEXT, status_from TEXT, status_to TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS indicator_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id INTEGER, kind TEXT, indicator TEXT, unit TEXT,
    baseline REAL, target REAL, value REAL, baseline_date TEXT, measured_at TEXT,
    evidence TEXT, recorded_by TEXT, is_simulated INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, user_name TEXT, role TEXT, action TEXT, detail TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS match_review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT, kind TEXT, academic_year TEXT, district TEXT, block TEXT, name_variant TEXT,
    candidates TEXT, payload TEXT, n_rows INTEGER, status TEXT,
    resolved_udise TEXT, resolved_by TEXT, resolved_at TEXT
);
"""


def engine() -> Engine:
    global _engine
    if _engine is None:
        path = Path(settings()["warehouse_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

        init_app_tables()
    return _engine


def init_app_tables() -> None:
    with _lock, engine().begin() as conn:
        for stmt in APP_TABLES.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))


def reset_engine() -> None:
    """Used by tests/eval to point at a different warehouse file."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    settings.cache_clear()
    bump_version()


def table_exists(name: str) -> bool:
    with engine().connect() as conn:
        r = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name})
        return r.first() is not None


def read_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def write_df(df: pd.DataFrame, table: str, if_exists: str = "replace") -> None:
    with _lock, engine().begin() as conn:
        df.to_sql(table, conn, if_exists=if_exists, index=False, chunksize=5000)


def execute(sql: str, params: dict | None = None) -> int | None:
    with _lock, engine().begin() as conn:
        r = conn.execute(text(sql), params or {})
        return r.lastrowid


def query(sql: str, params: dict | None = None) -> list[dict]:
    with engine().connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]


def version() -> int:
    """Monotonic warehouse version; analytics caches key on it."""
    return _version["n"]


def bump_version() -> None:
    _version["n"] += 1


def dumps(obj) -> str:
    return json.dumps(obj, default=str)
