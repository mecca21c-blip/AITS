# AITS Journal Writer Preview v1

Status: Preview Writer Skeleton
Scope: Standalone Unified Trading Journal dict-to-SQLite writer

---

## 1. Purpose

Journal Writer Preview v1 stores a Unified Trading Journal record dictionary into the Journal SQLite DB.

This is a standalone preview writer. It exists so future Journal Writer Preview, dataset builders, Local AI Shadow Evaluator, and review tools can share one storage path.

It is not connected to live application flow.

---

## 2. Preview Writer Scope

Supported:

- minimal record validation
- recursive sanitize
- journal record JSON storage
- compact index extraction
- preview write audit
- single-record load for smoke tests
- recent index list for preview verification

Not supported in this Sprint:

- Router auto-write
- UI button or screen integration
- Runtime loop integration
- Execution/Order integration
- AI provider calls
- LightGBM dataset builder
- Local AI training

---

## 3. Storage Module

Module:

```text
app/storage/journal_store.py
```

Added helpers:

- `sanitize_journal_record(record)`
- `validate_journal_record_minimal(record)`
- `extract_journal_index(record)`
- `append_journal_record_preview(record, db_path=None)`
- `load_journal_record(journal_id, db_path=None)`
- `list_journal_index(db_path=None, limit=50)`

---

## 4. Sanitize Policy

The preview writer sanitizes records before storing JSON.

Sensitive key names are removed recursively from the stored copy.

Examples:

- `api_key`
- `openai_api_key`
- `gemini_api_key`
- `upbit_access_key`
- `upbit_secret_key`
- `access_key`
- `secret_key`
- `secret`
- `token`
- `authorization`
- `raw_order_secret`
- `raw_private_detail`
- `account_secret`

Policy:

- caller record is not mutated
- sanitized copy is stored
- sensitive key/value pairs are removed from stored JSON
- key body, prefix, suffix, account secret, and payload secrets are never logged

Future writer integrations must keep this sanitize step before writing `record_json`.

---

## 5. Minimal Validation Policy

The preview writer requires a dictionary with:

- `schema`
- `journal_id`
- `created_at`
- `provider`
- `engine_role`

Required schema:

```text
aits_unified_trading_journal.v1
```

Missing fields raise `ValueError`.

Validation only confirms the minimum storage contract. Full business validation remains a future writer/review responsibility.

---

## 6. Storage Flow

`append_journal_record_preview()` performs:

1. initialize Journal SQLite DB
2. validate minimal Unified Trading Journal fields
3. sanitize the record
4. extract compact index fields
5. upsert into `journal_records`
6. upsert into `journal_index`
7. insert `journal_write_audit` event
8. return `journal_id`

All writes are local SQLite writes only.

---

## 7. journal_records

`journal_records` stores the sanitized full record JSON.

Upsert key:

```text
journal_id
```

Stored JSON uses:

```text
ensure_ascii=False
```

This preserves Korean text while keeping secrets redacted.

---

## 8. journal_index

`journal_index` stores compact search fields extracted from the record.

Extracted fields include:

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

The index is for filtering and future dataset construction. It is not an execution signal.

---

## 9. journal_write_audit

Preview writer audit event:

```text
event_type = preview_write
```

Success status:

```text
status = success
```

Failure status:

```text
status = failure
```

Audit messages are compact and must not contain API keys, private account details, raw order secrets, or full AI payloads.

---

## 10. Current Disconnected State

This writer is intentionally not wired into:

- UI
- DecisionRouter
- AIDecisionService
- Runtime loop
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard

No current app action automatically writes to the Journal DB.

---

## 11. Future Connections

Expected follow-up Sprints:

- AI-ARCH-08 GPT/Gemini Distillation Sample Builder
- AI-ARCH-09 Local AI Shadow Evaluator
- AI-ARCH-10 LightGBM Dataset Builder Preview

Before any runtime writer connection, AITS needs:

- sanitize confirmation
- writer source attribution
- preview/shadow/executed separation
- Router/Risk Guard safety review

---

## 12. Safety / Governance

Journal Writer Preview must never:

- call Router
- call Execution
- submit orders
- change action
- change confidence
- change ETA
- call GPT/Gemini/Local AI
- bypass Risk Guard
- store API keys
- store Upbit secrets
- store OpenAI/Gemini keys
- store raw account/private details
- store raw order secrets

The writer stores records for preview/review/learning infrastructure only.

Basic Preview and AI Output must remain separate in the Journal record.
