# AITS LightGBM Trainer Skeleton v1

Status: Trainer Skeleton
Scope: Dry-run LightGBM trainer contract for Local AI ML Engine

---

## 1. Purpose

The LightGBM Trainer Skeleton defines the structure of the future Local AI ML Engine training pipeline.

It validates LightGBM dataset preview rows and creates:

- trainer run summary
- artifact manifest
- evaluation report skeleton
- Local AI Model Registry entry skeleton

It does not train a model.

It does not create a model binary.

It does not add a LightGBM dependency.

---

## 2. Trainer Skeleton Definition

The trainer skeleton is a dry-run interface.

It checks whether dataset rows look structurally ready for future training.

It produces metadata that can later connect to:

- Local AI Model Registry
- evaluation reports
- artifact manifests
- trainer dependency gate

---

## 3. Not Real LightGBM Training

This Sprint explicitly does not:

- import LightGBM
- install LightGBM
- modify requirements
- train a model
- create model artifact binaries
- approve any model
- connect to live trading

---

## 4. Trainer Run Summary Schema

Schema:

```text
aits_lightgbm_trainer_run_summary.v1
```

Main sections:

- `trainer`
- `dataset`
- `training_plan`
- `artifact`
- `evaluation_report`
- `model_registry_entry`
- `safety`
- `meta`

Safety defaults:

- `live_trading_enabled=false`
- `router_connected=false`
- `execution_connected=false`
- `model_auto_approved=false`

---

## 5. Artifact Manifest Schema

Schema:

```text
aits_model_artifact_manifest.v1
```

Purpose:

Tracks what would have been created by a future trainer.

Dry-run defaults:

- `artifact_type=dry_run_manifest`
- `artifact_path=null`
- `checksum=null`
- `binary_created=false`

No model binary is created in this Sprint.

---

## 6. Evaluation Report Skeleton

Schema:

```text
aits_model_evaluation_report.v1
```

Metrics are present but null:

- accuracy
- precision
- recall
- f1
- pnl_proxy
- drawdown_proxy
- false_buy_rate
- false_sell_rate
- missed_opportunity_rate

Approval status:

```text
shadow_only
```

Decision summary:

```text
dry_run_only_no_training_executed
```

---

## 7. Model Registry Entry Skeleton

The registry entry follows AI-ARCH-04 Local AI Model Registry fields.

Defaults:

- `provider=local_ai`
- `runtime=lightgbm`
- `version=0.0.0-dry-run`
- `status=draft`
- `artifact_path=null`
- `checksum=null`

Notes:

- `dry_run_trainer_skeleton_only`
- `no_model_binary_created`
- `not_approved_for_live`

---

## 8. Dataset Row Input

Input rows follow:

```text
aits_lightgbm_dataset_row.v1
```

Expected sections:

- `features`
- `labels`
- `targets`
- `quality`

Only feature columns are used as feature candidates.

Labels and targets are used for validation only.

Raw Journal dumps, raw OHLCV, API keys, and secrets are prohibited.

---

## 9. Dry-run Validation

Validation checks:

- dataset is not empty
- at least one `usable_for_training` row exists
- at least one feature column exists
- target name exists in at least one usable row
- usable rows meet `min_rows`

Statuses:

- `validated`
- `dry_run_only`
- `rejected`

`dry_run_only` can still produce summaries and manifests.

---

## 10. Dependency Policy

The trainer summary explicitly records:

```json
{
  "lightgbm_required": false,
  "lightgbm_available": false,
  "dependency_added": false
}
```

Real dependency checks belong to a future dependency gate Sprint.

---

## 11. Safety / Privacy

The trainer skeleton must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- raw Journal record dumps
- raw OHLCV bulk data

Trainer summaries are planning artifacts, not trading signals.

Model registry entries generated here are drafts, not approved models.

---

## 12. Current Disconnected State

This trainer skeleton is not wired into:

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
- Local AI scheduler

---

## 13. Future Connections

Possible follow-up Sprints:

- AI-ARCH-13 LightGBM Dependency Gate
- Real Trainer Prototype
- Model Registry persistence
- Evaluation report persistence
- Dataset quality review

---

## 14. Prohibited Connections

This Sprint explicitly prohibits:

- Router auto connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- dependency changes
- model binary generation
- automatic training scheduler
