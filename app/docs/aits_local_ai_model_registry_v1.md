# AITS Local AI Model Registry v1

Status: Current Local AI Model Registry Definition
Scope: Local AI model artifacts, runtimes, feature schemas, datasets, evaluation reports, and deployment policy

---

## 1. Document Purpose

The Local AI Model Registry is the SSOT for Local AI models, runtimes, and learning artifacts.

It tracks:

- Which model was trained
- Which data was used
- Which feature schema was used
- Which runtime is required
- How the model was evaluated
- Whether the model is approved, shadow-only, deprecated, or archived

The Registry defines the basis for model replacement, rollback, verification, and approval.

---

## 2. Registry Philosophy

Local AI is not a single model file.

Local AI is a composition of:

- Reason Runtime
- ML Engine
- Feature Schema
- Memory DB
- Unified Trading Journal
- Policy Snapshot

Ollama is not a provider.

Ollama may be an optional development runtime, but the user distribution must not require external Ollama installation.

The production provider remains:

```text
provider=local_ai
```

Runtime and model are tracked separately.

---

## 3. Registry Top-Level Structure

```json
{
  "schema": "aits_local_ai_model_registry.v1",
  "registry_id": "...",
  "created_at": "...",
  "updated_at": "...",
  "active_model_id": "...",
  "models": [],
  "runtimes": [],
  "feature_schemas": [],
  "datasets": [],
  "evaluation_reports": [],
  "deployment_policy": {},
  "safety": {},
  "meta": {}
}
```

---

## 4. Model Entry Structure

Each model entry includes:

- model_id
- model_name
- model_type
- provider
- runtime
- base_model
- version
- status
- created_at
- updated_at
- artifact_path
- checksum
- feature_schema_id
- dataset_id
- evaluation_report_id
- notes

Allowed `model_type` values:

- reason_runtime
- lightgbm_ranker
- lightgbm_classifier
- lightgbm_regressor
- embedding_model
- hybrid_policy_model

Allowed `provider` value:

- local_ai

Allowed `runtime` values:

- embedded_llm
- ollama_dev
- lightgbm
- sklearn_compatible

Allowed `status` values:

- draft
- training
- evaluated
- shadow
- approved
- deprecated
- archived

`base_model` may use Qwen-family identifiers for reason runtime entries.

---

## 5. Runtime Entry Structure

Runtime entries include:

- runtime_id
- runtime_type
- runtime_name
- runtime_version
- device_target
- required_external_install
- dev_only
- supported_model_types
- safety_notes

Allowed `device_target` values:

- cpu
- gpu_optional

Default:

```json
{
  "required_external_install": false
}
```

Ollama development runtimes must use:

```json
{
  "runtime_type": "ollama_dev",
  "required_external_install": true,
  "dev_only": true
}
```

Ollama must not be documented as a mandatory user runtime.

---

## 6. Dataset Entry Structure

Datasets connect the Model Registry to the Unified Trading Journal.

Fields:

- dataset_id
- source_schema
- source_filter
- record_count
- date_range
- teacher_signal_source
- student_signal_source
- excluded_records_reason
- privacy_filter_applied
- created_at

Required `source_schema`:

```text
aits_unified_trading_journal.v1
```

`source_filter` may include:

- provider
- engine_role
- timeframe
- label_ready
- outcome_required

Allowed `teacher_signal_source` values:

- openai
- gemini
- human_review

Allowed `student_signal_source` values:

- local_ai

Datasets must not include API keys, raw account secrets, or unbounded raw logs.

---

## 7. Feature Schema Link

Feature schema entries include:

- feature_schema_id
- schema_name
- schema_version
- target_model_type
- input_groups
- compatible_model_ids

Allowed `input_groups`:

- market_features
- technical_features
- portfolio_features
- risk_features
- ai_output_features
- outcome_features

Feature schema compatibility must be explicit before training or evaluation.

---

## 8. Evaluation Report Structure

Evaluation report entries include:

- evaluation_report_id
- model_id
- dataset_id
- metrics
- benchmark_model_id
- evaluation_period
- decision_summary
- approval_status
- reviewer
- created_at

Metrics may include:

- accuracy
- precision
- recall
- f1
- pnl_proxy
- drawdown_proxy
- false_buy_rate
- false_sell_rate
- missed_opportunity_rate

Allowed `approval_status` values:

- rejected
- shadow_only
- approved_for_preview
- approved_for_recommendation

Allowed `reviewer` values:

- system
- user
- codex_report

---

## 9. Deployment Policy

Default deployment mode is preview/shadow only.

Local AI models are not automatically applied to live trading.

Approved models still must not bypass:

- Router
- Risk Guard
- Execution Layer
- User safety policy

The Registry keeps `active_model_id` so model replacement and rollback remain possible.

Deprecated models may be retained for review, replay, and audit purposes.

---

## 10. Safety / Governance

Rules:

- Do not store API keys.
- Do not store raw account secrets.
- Do not store personal or sensitive information.
- Do not store full raw OHLCV history in model metadata.
- Separate model artifacts from dataset metadata.
- Do not apply unapproved models to live flows.
- Local AI must not automatically change policy.
- Policy changes require user approval or Shadow verification.

---

## 11. Relationship With AI-ARCH-03

The Unified Trading Journal is the source of learning records.

The Local AI Model Registry is the SSOT for learning artifacts and model state.

Journal answers:

"What happened?"

Registry answers:

"Which model was made from which records?"

The Journal stores records; the Registry stores model lineage, evaluation, and deployment status.

---

## 12. Future Connected Sprints

AI-ARCH-05:

LightGBM Feature Schema

AI-ARCH-06:

Journal SQLite Skeleton

AI-ARCH-07:

Journal Writer Preview

AI-ARCH-08:

GPT/Gemini Distillation Sample Builder

AI-ARCH-09:

Local AI Shadow Evaluator
