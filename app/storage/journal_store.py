"""SQLite schema skeleton for the AITS Unified Trading Journal.

This module only creates the storage skeleton. It is not connected to runtime
writers, Router decisions, OrderAdapter, ExecutionBridge, Risk Guard, or live
trading paths. It does not convert AI judgement into orders.

Never store API keys, account secrets, raw private account details, or order
secrets in the journal database.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

JOURNAL_DB_FILENAME = "aits_journal.sqlite3"
SQLITE_SCHEMA_NAME = "aits_journal_sqlite.v1"
SQLITE_SCHEMA_VERSION = "1.0.0"
JOURNAL_RECORD_SCHEMA = "aits_unified_trading_journal.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_default_journal_db_path() -> Path:
    """Return the default journal DB path under the project data directory."""

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / JOURNAL_DB_FILENAME


def ensure_journal_db(db_path: Optional[Path] = None) -> Path:
    """Create the journal SQLite database and schema if needed.

    The returned path points to an initialized SQLite file. No journal records
    are written by this helper.
    """

    path = Path(db_path) if db_path is not None else get_default_journal_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        init_journal_schema(conn)
        conn.commit()
    return path


def init_journal_schema(conn: sqlite3.Connection) -> None:
    """Initialize the Journal SQLite v1 schema on an open connection."""

    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS journal_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            session_id TEXT,
            symbol TEXT,
            asset_name TEXT,
            timeframe TEXT,
            provider TEXT NOT NULL,
            engine_role TEXT NOT NULL,
            record_status TEXT NOT NULL DEFAULT 'preview',
            label_ready INTEGER NOT NULL DEFAULT 0,
            outcome_ready INTEGER NOT NULL DEFAULT 0,
            review_ready INTEGER NOT NULL DEFAULT 0,
            schema_name TEXT NOT NULL DEFAULT 'aits_unified_trading_journal.v1',
            schema_version TEXT NOT NULL DEFAULT '1.0.0',
            record_json TEXT NOT NULL,
            created_unix INTEGER,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS journal_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            symbol TEXT,
            provider TEXT,
            engine_role TEXT,
            final_action TEXT,
            ai_action TEXT,
            router_allowed INTEGER,
            shadow_only INTEGER,
            preview_only INTEGER,
            executed INTEGER,
            label_ready INTEGER,
            pnl_bucket TEXT,
            review_result TEXT,
            risk_level TEXT,
            market_regime TEXT
        );

        CREATE TABLE IF NOT EXISTS journal_schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal_write_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT NOT NULL,
            event_type TEXT NOT NULL,
            journal_id TEXT,
            status TEXT NOT NULL,
            message TEXT,
            meta_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_journal_records_created_at
            ON journal_records (created_at);
        CREATE INDEX IF NOT EXISTS idx_journal_records_symbol
            ON journal_records (symbol);
        CREATE INDEX IF NOT EXISTS idx_journal_records_provider
            ON journal_records (provider);
        CREATE INDEX IF NOT EXISTS idx_journal_records_label_ready
            ON journal_records (label_ready);
        CREATE INDEX IF NOT EXISTS idx_journal_index_symbol
            ON journal_index (symbol);
        CREATE INDEX IF NOT EXISTS idx_journal_index_provider
            ON journal_index (provider);
        CREATE INDEX IF NOT EXISTS idx_journal_index_created_at
            ON journal_index (created_at);
        """
    )
    set_schema_version(conn, SQLITE_SCHEMA_VERSION)
    _set_schema_meta(conn, "schema_name", SQLITE_SCHEMA_NAME)
    _set_schema_meta(conn, "journal_record_schema", JOURNAL_RECORD_SCHEMA)


def get_schema_version(conn: sqlite3.Connection) -> str | None:
    """Return the initialized SQLite schema version, if present."""

    try:
        row = conn.execute(
            "SELECT value FROM journal_schema_meta WHERE key = ?",
            ("schema_version",),
        ).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row else None


def set_schema_version(conn: sqlite3.Connection, version: str) -> None:
    """Set the SQLite schema version metadata."""

    _set_schema_meta(conn, "schema_version", version)


def _set_schema_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO journal_schema_meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, _utc_now()),
    )


__all__ = [
    "JOURNAL_DB_FILENAME",
    "JOURNAL_RECORD_SCHEMA",
    "SQLITE_SCHEMA_NAME",
    "SQLITE_SCHEMA_VERSION",
    "ensure_journal_db",
    "get_default_journal_db_path",
    "get_schema_version",
    "init_journal_schema",
    "set_schema_version",
]
