# AITS Local AI Evaluation Dashboard Preview v1

Status: Report Builder Preview
Scope: Local AI learning/comparison pipeline summary

---

## 1. Purpose

The Local AI Evaluation Dashboard Preview summarizes the current state of Local AI learning and comparison artifacts.

It consumes:

- GPT/Gemini distillation samples
- Local AI shadow evaluation results
- LightGBM dataset preview rows

It produces:

- summary dict
- JSON report
- Markdown report

---

## 2. Dashboard Preview Definition

This is not a GUI dashboard.

It is a standalone report builder that prepares the information a future dashboard could display.

It does not run training.

It does not run inference.

It does not connect to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 3. Summary Schema

Schema:

```text
aits_local_ai_evaluation_dashboard_preview.v1
```

Top-level sections:

- `scope`
- `distillation`
- `shadow_evaluation`
- `dataset`
- `safety`
- `readiness`
- `meta`

---

## 4. Distillation Summary

Distillation summary covers GPT/Gemini teacher sample state.

Fields:

- `total_samples`
- `usable_samples`
- `excluded_samples`
- `teacher_provider_distribution`
- `label_ready_count`
- `outcome_ready_count`
- `review_ready_count`
- `avg_sample_weight_hint`

Usable sample condition:

```text
quality.usable_for_distillation == true
```

---

## 5. Shadow Evaluation Summary

Shadow summary covers teacher/student agreement.

Fields:

- `total_evaluations`
- `usable_evaluations`
- `agreement_score_avg`
- `agreement_score_min`
- `agreement_score_max`
- `action_match_rate`
- `intent_match_rate`
- `safety_match_rate`
- `severity_distribution`
- `review_recommended_count`
- `critical_count`
- `warning_count`

Usable evaluation condition:

```text
quality.usable_for_shadow_eval == true
```

---

## 6. Dataset Summary

Dataset summary covers LightGBM dataset preview row state.

Fields:

- `total_rows`
- `training_usable_count`
- `inference_preview_usable_count`
- `provider_distribution`
- `engine_role_distribution`
- `label_ready_count`
- `target_available_count`
- `sample_weight_avg`
- `excluded_reason_distribution`

Training usable condition:

```text
quality.usable_for_training == true
```

---

## 7. Safety Flags

Safety detection is conservative string-based scanning in v1.

Flags:

- `raw_secret_detected`
- `leakage_risk_detected`
- `execution_link_detected`
- `ui_link_detected`

Markers include:

- `api_key`
- `secret_key`
- `authorization`
- `SHOULD_NOT_BE_STORED`
- `raw_future_candles`
- `pnl_after_`
- `hit_take_profit`
- `human_review_score`
- `OrderAdapter`
- `ExecutionBridge`
- `app_gui`
- `PySide6`

False positives are possible. Safety flags mean review is required, not that runtime behavior changed.

---

## 8. Readiness Levels

Readiness levels:

- `empty`
- `insufficient`
- `preview_ready`
- `training_candidate_ready`
- `review_required`

General rules:

- empty: no preview artifacts
- insufficient: not enough samples or dataset rows
- preview_ready: enough preview artifacts for review
- training_candidate_ready: at least 100 training usable rows and no safety flags
- review_required: safety flags or many critical shadow evaluations

`local_ai_training_recommended=True` is not automatic training approval.

Actual training requires a separate Goal.

---

## 9. JSON Export

Helper:

```text
export_dashboard_summary_json()
```

Rules:

- UTF-8
- `ensure_ascii=False`
- `indent=2`
- parent directory may be created
- sensitive key-like fields removed before export

---

## 10. Markdown Export

Helper:

```text
export_dashboard_summary_markdown()
```

Report sections:

- Title
- Readiness
- Distillation Summary
- Shadow Evaluation Summary
- Dataset Summary
- Safety Flags
- Next Recommended Action

Markdown is for human review and planning only.

---

## 11. Current Disconnected State

This builder is not wired into:

- PySide6 GUI
- app_gui.py
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

---

## 12. Future Connections

Possible follow-up Sprints:

- AI-ARCH-12 LightGBM Trainer Skeleton
- AI-ARCH-11-B UI Preview
- Local AI Evaluation Dashboard screen
- Model Registry evaluation report integration

---

## 13. Safety / Privacy

Dashboard summaries must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- raw Journal record dumps
- raw OHLCV bulk data

Readiness is a planning signal, not a trade signal.

Dashboard output must not bypass:

- Router
- Risk Guard
- Execution Layer

---

## 14. Prohibited Connections

This Sprint explicitly prohibits:

- Router auto connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- model training execution
- external AI provider calls
- dependency changes
