# AITS Journal SQLite Skeleton v1

Status: Storage Skeleton
Scope: SQLite schema initialization for the Unified Trading Journal

---

## 1. Purpose

This document defines the minimal SQLite storage skeleton for the AITS Unified Trading Journal.

The current scope is limited to:

- DB path definition
- schema initialization
- metadata version tracking
- future writer audit table preparation

This Sprint does not connect the Journal to:

- UI
- DecisionRouter
- Runtime loop
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard
- GPT/Gemini calls
- Local AI training

---

## 2. DB File

Default file:

```text
data/aits_journal.sqlite3
```

The storage module exposes a path argument so tests and future tools can initialize an isolated journal DB without changing runtime state.

---

## 3. Storage Module

Module:

```text
app/storage/journal_store.py
```

Main helpers:

- `get_default_journal_db_path()`
- `ensure_journal_db(db_path=None)`
- `init_journal_schema(conn)`
- `get_schema_version(conn)`
- `set_schema_version(conn, version)`

The module only creates schema. It does not write runtime journal records.

---

## 4. Tables

### 4-1. journal_records

Role:

Stores the full Unified Trading Journal record as JSON.

Key fields:

- `journal_id`
- `created_at`
- `session_id`
- `symbol`
- `asset_name`
- `timeframe`
- `provider`
- `engine_role`
- `record_status`
- `label_ready`
- `outcome_ready`
- `review_ready`
- `schema_name`
- `schema_version`
- `record_json`

`record_json` stores the full `aits_unified_trading_journal.v1` record.

Before future writer integration, records must be sanitized so API keys, account secrets, raw private account details, and order secrets are never stored.

---

### 4-2. journal_index

Role:

Stores compact searchable fields for filtering and future dataset building.

Key fields:

- `journal_id`
- `created_at`
- `symbol`
- `provider`
- `engine_role`
- `final_action`
- `ai_action`
- `router_allowed`
- `shadow_only`
- `preview_only`
- `executed`
- `label_ready`
- `pnl_bucket`
- `review_result`
- `risk_level`
- `market_regime`

The index is intended to mirror journal records at a compact level. It does not replace `journal_records.record_json`.

---

### 4-3. journal_schema_meta

Role:

Stores SQLite schema metadata and compatible Journal record schema information.

Required keys:

- `schema_name = aits_journal_sqlite.v1`
- `schema_version = 1.0.0`
- `journal_record_schema = aits_unified_trading_journal.v1`

---

### 4-4. journal_write_audit

Role:

Reserved for future Journal Writer Preview audit events.

Current Sprint:

- table only
- no runtime audit writer
- no Router/UI/Execution connection

---

## 5. Indexes

Initial indexes:

- `idx_journal_records_created_at`
- `idx_journal_records_symbol`
- `idx_journal_records_provider`
- `idx_journal_records_label_ready`
- `idx_journal_index_symbol`
- `idx_journal_index_provider`
- `idx_journal_index_created_at`

These are intended for basic filtering by time, symbol, provider, and learning readiness.

---

## 6. Unified Trading Journal Relationship

The SQLite skeleton stores records defined by:

```text
aits_unified_trading_journal.v1
```

Journal records remain the SSOT for:

- Basic snapshot
- AI input contract
- AI output contract
- recommendation candidate
- Router validation
- execution state
- outcome
- review
- learning label
- safety metadata

Basic Preview and AI Output must remain separate.

---

## 7. Local AI Model Registry Relationship

The Local AI Model Registry tracks which model was trained, evaluated, approved, or deprecated.

The Journal SQLite DB stores the source records that can later become datasets for those models.

Relationship:

```text
Unified Trading Journal records
→ Dataset metadata
→ Model Registry dataset_id / feature_schema_id
→ Evaluation reports
```

The registry answers:

```text
Which model was created from which Journal records?
```

---

## 8. LightGBM Feature Schema Relationship

The LightGBM Feature Schema defines how Journal records are converted into feature vectors.

The SQLite skeleton does not extract features.

Future flow:

```text
journal_records.record_json
→ leakage filter
→ feature vector
→ label
→ LightGBM dataset
```

Outcome and review fields must not be used as inference input.

---

## 9. Current Disconnected State

This Sprint intentionally does not connect Journal SQLite to live application flow.

No current code path writes:

- Router result
- AI output
- Execution result
- Order result
- UI event

to the Journal DB.

The next expected connection Sprint is:

```text
AI-ARCH-07 Journal Writer Preview
```

---

## 10. Safety / Governance

The Journal DB must never store:

- API keys
- Upbit access key
- Upbit secret key
- OpenAI key
- Gemini key
- raw account secrets
- raw private account details
- raw order secrets
- full raw OHLCV bulk data

Future writer integration must include a sanitize stage before writing `record_json`.

Preview, shadow, dry-run, recommendation, validated, and executed states must remain clearly separated.

Current safety defaults:

- storage skeleton only
- no order execution
- no Runtime application
- no Router application
- no Risk Guard bypass
- no AI API call
- no training execution

---

## 11. Future Sprint

Planned follow-up:

- AI-ARCH-07 Journal Writer Preview
- AI-ARCH-08 GPT/Gemini Distillation Sample Builder
- AI-ARCH-09 Local AI Shadow Evaluator
- AI-ARCH-10 LightGBM Dataset Builder Preview
