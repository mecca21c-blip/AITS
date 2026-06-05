# AITS Distillation Sample Builder v1

Status: Preview Builder Skeleton
Scope: GPT/Gemini Journal records to Local AI teacher samples

---

## 1. Purpose

The Distillation Sample Builder converts GPT/Gemini Unified Trading Journal records into compact teacher samples for future Local AI comparison, evaluation, and training.

This builder does not call OpenAI or Gemini.

It does not train Local AI.

It does not connect to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 2. Distillation Sample Definition

A distillation sample is a compact record that separates:

- teacher signal from GPT/Gemini
- student context for Local AI
- labels and readiness state
- quality and exclusion status

Schema:

```text
aits_distillation_sample.v1
```

---

## 3. Teacher / Student Concept

Teacher:

- GPT/OpenAI
- Gemini

Student:

- Local AI

Teacher samples let Local AI later compare its output against GPT/Gemini reasoning without treating Basic Preview as AI judgement.

---

## 4. GPT/Gemini Teacher Signal

Teacher fields are selected from `ai_output_contract`:

- `action`
- `confidence`
- `intent`
- `scenario`
- `why`
- `eta`
- `safety`

Fallback:

- `recommendation.ai_action` may be used if `ai_output_contract.action` is absent.

Only provider values below are teacher providers:

- `openai`
- `gemini`

---

## 5. Local AI Student Context

Student context is compact input context that Local AI may later use for comparison or learning.

Included groups:

- `market_snapshot`
- `basic_snapshot`
- `portfolio_context`
- `router_context`

The builder does not include the original Journal record as raw metadata.

---

## 6. Sample Schema Example

```json
{
  "schema": "aits_distillation_sample.v1",
  "sample_id": "distill-teacher-openai-001",
  "source_journal_id": "teacher-openai-001",
  "created_at": "...",
  "source_provider": "openai",
  "source_engine_role": "preview",
  "symbol": "KRW-BTC",
  "timeframe": "5m",
  "teacher": {
    "action": "observe",
    "confidence": 0.71,
    "intent": {},
    "scenario": {},
    "why": {},
    "eta": {},
    "safety": {}
  },
  "student_context": {
    "market_snapshot": {},
    "basic_snapshot": {},
    "portfolio_context": {},
    "router_context": {}
  },
  "labels": {
    "label_ready": false,
    "outcome_ready": false,
    "review_ready": false,
    "label_action_quality": null,
    "label_pnl_bucket": null
  },
  "quality": {
    "usable_for_distillation": true,
    "excluded_reason": null,
    "sample_weight_hint": 1.0
  },
  "meta": {}
}
```

---

## 7. Journal DB Read Conditions

Builder helper:

```text
load_teacher_records_from_journal()
```

Default providers:

- `openai`
- `gemini`

Supported filters:

- `require_label_ready`
- `require_outcome_ready`
- `require_review_ready`
- `limit`

Records are read from `journal_records.record_json` ordered by `created_at DESC`.

---

## 8. JSONL Export Policy

Builder helper:

```text
export_distillation_samples_jsonl()
```

Rules:

- one sample per line
- UTF-8
- `ensure_ascii=False`
- parent directory may be created

JSONL export is a data handoff format only. It is not a training command.

---

## 9. Label / Outcome / Review Readiness

`label_ready` comes from:

```text
learning_label.label_ready
```

`outcome_ready` is true when an outcome object exists.

`review_ready` is true when a review object exists.

Supervised Local AI training should use only records whose label policy is explicitly satisfied by a later dataset builder.

---

## 10. sample_weight_hint

Default:

```text
1.0
```

Adjustments:

- `label_ready=True`: +0.2
- `outcome_ready=True`: +0.2
- `review_ready=True`: +0.3

Maximum:

```text
1.5
```

This is only a hint. Final sample weighting belongs to a future dataset builder.

---

## 11. Safety / Privacy

The builder must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account detail
- raw order secrets
- full raw OHLCV arrays
- raw Journal record dumps

Distillation samples are teacher signals, not order commands.

Local AI must not use these samples to bypass:

- Router
- Risk Guard
- Execution Layer

---

## 12. Current Disconnected State

This builder is not wired into:

- UI
- Runtime loop
- DecisionRouter
- AIDecisionService
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard
- OpenAI/Gemini API calls
- Local AI training

All functions are standalone utilities.

---

## 13. Future Connections

Expected follow-up Sprints:

- AI-ARCH-09 Local AI Shadow Evaluator
- AI-ARCH-10 LightGBM Dataset Builder Preview
- GPT/Gemini Distillation Sample Builder export review
- Local AI teacher/student comparison dashboard
