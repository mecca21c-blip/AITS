# AITS Model Artifact / Registry Persistence Preview v1

Status: Persistence Preview
Scope: Local AI model artifact and registry JSON storage

---

## 1. Purpose

This document defines the preview persistence layer for Local AI model artifacts and registry entries.

It stores outputs from the LightGBM Trainer Skeleton as JSON files.

It does not train models.

It does not create model binaries.

It does not connect to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 2. Persistence Preview Definition

Persistence Preview provides local file storage for:

- trainer run summary
- artifact manifest
- evaluation report
- model registry entry
- registry index
- active model preview pointer

This is infrastructure for future model management, not a live model activation system.

---

## 3. Directory Structure

Default root:

```text
data/local_ai_registry
```

Structure:

```text
data/local_ai_registry/
  registry_index.json
  active_model.json
  models/
    {model_id}/
      model_registry_entry.json
      artifact_manifest.json
      evaluation_report.json
      trainer_run_summary.json
      notes.json
```

`notes.json` is reserved for future use.

---

## 4. registry_index.json

Schema:

```text
aits_local_ai_registry_index.v1
```

Example:

```json
{
  "schema": "aits_local_ai_registry_index.v1",
  "created_at": "...",
  "updated_at": "...",
  "active_model_id": null,
  "models": [
    {
      "model_id": "...",
      "model_name": "...",
      "model_type": "lightgbm_classifier",
      "provider": "local_ai",
      "runtime": "lightgbm",
      "status": "draft",
      "version": "0.0.0-dry-run",
      "feature_schema_id": "aits_lightgbm_feature_schema.v1",
      "dataset_id": "...",
      "evaluation_report_id": "...",
      "artifact_path": null,
      "binary_created": false,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "meta": {}
}
```

---

## 5. active_model.json

Schema:

```text
aits_active_local_ai_model.v1
```

Example:

```json
{
  "schema": "aits_active_local_ai_model.v1",
  "active_model_id": "...",
  "updated_at": "...",
  "mode": "preview",
  "notes": [
    "preview_pointer_only",
    "not_live_approved"
  ]
}
```

The active model pointer is preview-only.

It does not activate a model in Router or Execution.

---

## 6. Model Artifact File Set

Each model directory stores:

- `model_registry_entry.json`
- `artifact_manifest.json`
- `evaluation_report.json`
- `trainer_run_summary.json`

No model binary is created by this Sprint.

---

## 7. Save / Load / Upsert Flow

Main save helper:

```text
save_model_artifacts_preview()
```

Flow:

1. validate `model_id`
2. create `models/{model_id}`
3. save model registry entry
4. save artifact manifest
5. save evaluation report
6. save trainer run summary
7. upsert compact registry index entry
8. return persistence result

Load helper:

```text
load_model_artifacts_preview()
```

Index helper:

```text
upsert_registry_index_entry()
```

---

## 8. Active Model Preview Pointer

Helper:

```text
set_active_model_preview()
```

Rules:

- `mode` is always `preview`
- `not_live_approved` note is always included
- model id must already exist in registry index
- registry index `active_model_id` is updated

This does not approve the model for live trading.

---

## 9. AI-ARCH-12 Relationship

AI-ARCH-12 creates:

- Trainer Run Summary
- Artifact Manifest
- Evaluation Report Skeleton
- Model Registry Entry Skeleton

AI-ARCH-13 stores those objects and maintains a preview registry index.

---

## 10. AI-ARCH-04 Relationship

AI-ARCH-04 defines the official Local AI Model Registry structure.

This persistence preview stores a compact local file version of that registry.

The registry answers:

```text
Which dry-run model entry exists, and where are its metadata files?
```

---

## 11. Safety / Privacy

The persistence layer must not store:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- raw Journal record dumps
- raw OHLCV bulk data

`model_id` path traversal is prohibited.

`active_model_id` is a preview pointer only.

Status `approved` in a JSON file must not connect to Router or Execution by itself.

---

## 12. Current Disconnected State

This module is not wired into:

- UI
- Runtime loop
- DecisionRouter
- AIDecisionService
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard
- OpenAI/Gemini API calls
- Local AI inference
- LightGBM training
- model scheduler

---

## 13. Future Connections

Possible follow-up Sprints:

- AI-ARCH-14 LightGBM Dependency Gate
- AI-ARCH-15 Real Trainer Prototype
- Model Registry UI Preview
- Registry snapshot review
- Artifact checksum validation

---

## 14. Prohibited Connections

This Sprint explicitly prohibits:

- Router auto connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- model binary generation
- automatic training scheduler
- dependency changes
