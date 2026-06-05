"""SQLite schema skeleton for the AITS Unified Trading Journal.

This module only creates the storage skeleton. It is not connected to runtime
writers, Router decisions, OrderAdapter, ExecutionBridge, Risk Guard, or live
trading paths. It does not convert AI judgement into orders.

Never store API keys, account secrets, raw private account details, or order
secrets in the journal database.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

JOURNAL_DB_FILENAME = "aits_journal.sqlite3"
SQLITE_SCHEMA_NAME = "aits_journal_sqlite.v1"
SQLITE_SCHEMA_VERSION = "1.0.0"
JOURNAL_RECORD_SCHEMA = "aits_unified_trading_journal.v1"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "secret",
    "token",
    "authorization",
    "raw_order_secret",
    "raw_private_detail",
    "private_detail",
    "account_secret",
    "openai_api_key",
    "gemini_api_key",
    "upbit_access_key",
    "upbit_secret_key",
)


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
    conn = sqlite3.connect(path)
    try:
        init_journal_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def sanitize_journal_record(record: dict) -> dict:
    """Return a sanitized deep copy of a Journal record.

    This preview writer never mutates the caller's record. Sensitive key-like
    fields are removed before JSON storage.
    """

    if not isinstance(record, dict):
        raise TypeError("journal record must be a dict")
    return _sanitize_value(copy.deepcopy(record))


def validate_journal_record_minimal(record: dict) -> None:
    """Validate the minimal Unified Trading Journal v1 fields."""

    if not isinstance(record, dict):
        raise ValueError("journal record must be a dict")
    required = ("schema", "journal_id", "created_at", "provider", "engine_role")
    missing = [key for key in required if not record.get(key)]
    if missing:
        raise ValueError(f"journal record missing required fields: {', '.join(missing)}")
    if str(record.get("schema")) != JOURNAL_RECORD_SCHEMA:
        raise ValueError(
            f"journal record schema must be {JOURNAL_RECORD_SCHEMA}"
        )


def extract_journal_index(record: dict) -> dict:
    """Extract a compact searchable index from a sanitized Journal record."""

    recommendation = _dict_at(record, "recommendation")
    router_validation = _dict_at(record, "router_validation")
    ai_output = _dict_at(record, "ai_output_contract")
    execution = _dict_at(record, "execution")
    safety = _dict_at(record, "safety")
    learning_label = _dict_at(record, "learning_label")
    outcome = _dict_at(record, "outcome")
    review = _dict_at(record, "review")
    basic_snapshot = _dict_at(record, "basic_snapshot")
    market_snapshot = _dict_at(record, "market_snapshot")

    return {
        "journal_id": record.get("journal_id"),
        "created_at": record.get("created_at"),
        "symbol": record.get("symbol"),
        "provider": record.get("provider"),
        "engine_role": record.get("engine_role"),
        "final_action": recommendation.get("final_action")
        or router_validation.get("final_action"),
        "ai_action": ai_output.get("action") or recommendation.get("ai_action"),
        "router_allowed": _bool_to_int(router_validation.get("allowed")),
        "shadow_only": _bool_to_int(safety.get("shadow_only")),
        "preview_only": _bool_to_int(safety.get("preview_only")),
        "executed": _bool_to_int(execution.get("executed")),
        "label_ready": _bool_to_int(learning_label.get("label_ready")),
        "pnl_bucket": learning_label.get("label_pnl_bucket")
        or outcome.get("pnl_bucket"),
        "review_result": review.get("review_result"),
        "risk_level": safety.get("risk_level") or basic_snapshot.get("risk_level"),
        "market_regime": market_snapshot.get("market_regime"),
    }


def append_journal_record_preview(
    record: dict,
    db_path: Optional[Path] = None,
) -> str:
    """Store a Unified Trading Journal record through the preview writer.

    This function is intentionally standalone. It does not call Router,
    Runtime, OrderAdapter, ExecutionBridge, Risk Guard, or AI providers.
    """

    path = ensure_journal_db(db_path)
    journal_id = str(record.get("journal_id", "")) if isinstance(record, dict) else None
    conn = sqlite3.connect(path)
    try:
        validate_journal_record_minimal(record)
        sanitized = sanitize_journal_record(record)
        index = extract_journal_index(sanitized)
        _upsert_journal_record(conn, sanitized)
        _upsert_journal_index(conn, index)
        _insert_write_audit(
            conn,
            event_type="preview_write",
            status="success",
            journal_id=str(sanitized.get("journal_id")),
            message="preview journal record stored",
            meta={"provider": sanitized.get("provider")},
        )
        conn.commit()
        return str(sanitized["journal_id"])
    except Exception as exc:
        _insert_write_audit(
            conn,
            event_type="preview_write",
            status="failure",
            journal_id=journal_id,
            message=f"{type(exc).__name__}: {exc}",
            meta=None,
        )
        conn.commit()
        raise
    finally:
        conn.close()


def load_journal_record(
    journal_id: str,
    db_path: Optional[Path] = None,
) -> dict | None:
    """Load one sanitized Journal record by id for preview verification."""

    path = ensure_journal_db(db_path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT record_json FROM journal_records WHERE journal_id = ?",
            (journal_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return json.loads(str(row[0]))


def list_journal_index(
    db_path: Optional[Path] = None,
    limit: int = 50,
) -> list[dict]:
    """Return recent Journal index rows for preview verification."""

    path = ensure_journal_db(db_path)
    safe_limit = max(1, min(int(limit or 50), 500))
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT journal_id, created_at, symbol, provider, engine_role,
                   final_action, ai_action, router_allowed, shadow_only,
                   preview_only, executed, label_ready, pnl_bucket,
                   review_result, risk_level, market_regime
            FROM journal_index
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


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


def _sanitize_value(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                continue
            else:
                sanitized[key] = _sanitize_value(child)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _dict_at(record: dict, key: str) -> dict:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _bool_to_int(value) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _created_unix(created_at: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except Exception:
        return None


def _record_status(record: dict) -> str:
    meta = _dict_at(record, "meta")
    return str(meta.get("record_status") or "preview")


def _upsert_journal_record(conn: sqlite3.Connection, record: dict) -> None:
    now = _utc_now()
    created_at = str(record.get("created_at"))
    learning_label = _dict_at(record, "learning_label")
    outcome = _dict_at(record, "outcome")
    review = _dict_at(record, "review")
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
    conn.execute(
        """
        INSERT INTO journal_records (
            journal_id, created_at, session_id, symbol, asset_name, timeframe,
            provider, engine_role, record_status, label_ready, outcome_ready,
            review_ready, schema_name, schema_version, record_json,
            created_unix, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(journal_id) DO UPDATE SET
            created_at = excluded.created_at,
            session_id = excluded.session_id,
            symbol = excluded.symbol,
            asset_name = excluded.asset_name,
            timeframe = excluded.timeframe,
            provider = excluded.provider,
            engine_role = excluded.engine_role,
            record_status = excluded.record_status,
            label_ready = excluded.label_ready,
            outcome_ready = excluded.outcome_ready,
            review_ready = excluded.review_ready,
            schema_name = excluded.schema_name,
            schema_version = excluded.schema_version,
            record_json = excluded.record_json,
            created_unix = excluded.created_unix,
            updated_at = excluded.updated_at
        """,
        (
            record.get("journal_id"),
            created_at,
            record.get("session_id"),
            record.get("symbol"),
            record.get("asset_name"),
            record.get("timeframe"),
            record.get("provider"),
            record.get("engine_role"),
            _record_status(record),
            _bool_to_int(learning_label.get("label_ready")) or 0,
            _bool_to_int(outcome.get("outcome_ready") or bool(outcome)) or 0,
            _bool_to_int(review.get("review_ready") or bool(review)) or 0,
            JOURNAL_RECORD_SCHEMA,
            SQLITE_SCHEMA_VERSION,
            payload,
            _created_unix(created_at),
            now,
        ),
    )


def _upsert_journal_index(conn: sqlite3.Connection, index: dict) -> None:
    conn.execute(
        """
        INSERT INTO journal_index (
            journal_id, created_at, symbol, provider, engine_role, final_action,
            ai_action, router_allowed, shadow_only, preview_only, executed,
            label_ready, pnl_bucket, review_result, risk_level, market_regime
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(journal_id) DO UPDATE SET
            created_at = excluded.created_at,
            symbol = excluded.symbol,
            provider = excluded.provider,
            engine_role = excluded.engine_role,
            final_action = excluded.final_action,
            ai_action = excluded.ai_action,
            router_allowed = excluded.router_allowed,
            shadow_only = excluded.shadow_only,
            preview_only = excluded.preview_only,
            executed = excluded.executed,
            label_ready = excluded.label_ready,
            pnl_bucket = excluded.pnl_bucket,
            review_result = excluded.review_result,
            risk_level = excluded.risk_level,
            market_regime = excluded.market_regime
        """,
        (
            index.get("journal_id"),
            index.get("created_at"),
            index.get("symbol"),
            index.get("provider"),
            index.get("engine_role"),
            index.get("final_action"),
            index.get("ai_action"),
            index.get("router_allowed"),
            index.get("shadow_only"),
            index.get("preview_only"),
            index.get("executed"),
            index.get("label_ready"),
            index.get("pnl_bucket"),
            index.get("review_result"),
            index.get("risk_level"),
            index.get("market_regime"),
        ),
    )


def _insert_write_audit(
    conn: sqlite3.Connection,
    event_type: str,
    status: str,
    journal_id: str | None,
    message: str,
    meta: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO journal_write_audit (
            event_time, event_type, journal_id, status, message, meta_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_now(),
            event_type,
            journal_id,
            status,
            message,
            json.dumps(meta or {}, ensure_ascii=False, sort_keys=True),
        ),
    )


__all__ = [
    "JOURNAL_DB_FILENAME",
    "JOURNAL_RECORD_SCHEMA",
    "SQLITE_SCHEMA_NAME",
    "SQLITE_SCHEMA_VERSION",
    "append_journal_record_preview",
    "ensure_journal_db",
    "extract_journal_index",
    "get_default_journal_db_path",
    "get_schema_version",
    "init_journal_schema",
    "list_journal_index",
    "load_journal_record",
    "sanitize_journal_record",
    "set_schema_version",
    "validate_journal_record_minimal",
]
