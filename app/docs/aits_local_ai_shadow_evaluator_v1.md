# AITS Local AI Shadow Evaluator v1

Status: Shadow Evaluation Skeleton
Scope: Teacher distillation sample vs Local AI student output comparison

---

## 1. Purpose

The Local AI Shadow Evaluator compares a GPT/Gemini teacher distillation sample with a caller-provided Local AI student output.

The evaluator creates a shadow evaluation result for review, future dashboards, and future Local AI quality tracking.

It does not run Local AI inference.

It does not train Local AI.

It does not connect to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 2. Shadow Evaluator Definition

Shadow Evaluation is a preview-only comparison layer.

It answers:

- Did Local AI choose a similar action candidate?
- Did Local AI express a similar intent?
- Did Local AI preserve the same safety level?
- Is confidence close enough to the teacher?

It does not answer:

- whether to place an order
- whether to change Router action
- whether to bypass Risk Guard
- whether a model is approved for live use

---

## 3. Teacher / Student Comparison

Teacher:

- GPT/OpenAI distillation sample
- Gemini distillation sample

Student:

- Local AI output supplied by caller
- mock output for smoke tests
- future Local AI shadow inference output

The evaluator only compares objects passed into the function. It does not call providers or models.

---

## 4. Evaluation Result Schema

Schema:

```text
aits_local_ai_shadow_evaluation.v1
```

Example:

```json
{
  "schema": "aits_local_ai_shadow_evaluation.v1",
  "evaluation_id": "shadow-sample-001",
  "created_at": "...",
  "source_sample_id": "sample-001",
  "source_journal_id": "teacher-openai-001",
  "symbol": "KRW-BTC",
  "timeframe": "5m",
  "teacher_provider": "openai",
  "student_provider": "local_ai",
  "teacher": {
    "action": "observe",
    "confidence": 0.71,
    "intent_type": "wait_for_breakout",
    "safety_level": "normal"
  },
  "student": {
    "action": "observe",
    "confidence": 0.66,
    "intent_type": "wait_for_breakout",
    "safety_level": "normal"
  },
  "comparison": {
    "action_match": true,
    "confidence_delta": 0.05,
    "intent_match": true,
    "safety_match": true,
    "agreement_score": 0.99,
    "disagreement_reason": null
  },
  "quality": {
    "usable_for_shadow_eval": true,
    "excluded_reason": null,
    "severity": "info",
    "review_recommended": false
  },
  "labels": {},
  "meta": {}
}
```

---

## 5. Comparison Items

Compared fields:

- action
- confidence
- intent type
- safety level

Action normalization:

- `observe`, `wait`, `hold`, `stay`, `watch` become `observe`
- `buy`, `buy_candidate`, `entry`, `entry_candidate` become `buy_candidate`
- `sell`, `reduce`, `exit` variants become `sell_or_reduce_candidate`

These normalized values are comparison labels, not order commands.

---

## 6. agreement_score

Scoring weights:

- action match: `0.45`
- intent match: `0.20`
- safety match: `0.15`
- confidence closeness: up to `0.20`

Confidence closeness:

```text
max(0, 1 - abs(teacher_confidence - student_confidence)) * 0.20
```

Total score range:

```text
0.0 ~ 1.0
```

The score is an evaluation metric, not a trading signal.

---

## 7. Severity

Severity rules:

- `agreement_score >= 0.75`: `info`
- `0.45 <= agreement_score < 0.75`: `warning`
- `agreement_score < 0.45`: `critical`
- unusable sample/student signal: `critical`

---

## 8. review_recommended

Review is recommended when:

- action mismatch
- severity is `critical`
- sample is not usable for shadow evaluation
- student signal is missing

Review recommendation is for diagnostics only.

---

## 9. JSONL Export

Helper:

```text
export_shadow_evaluations_jsonl()
```

Rules:

- one result per line
- UTF-8
- `ensure_ascii=False`
- parent directory may be created
- sensitive key-like fields are removed during export

---

## 10. Current Disconnected State

This evaluator is not wired into:

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
- Local AI training

The smoke-test mock helper is not a model.

---

## 11. Future Connections

Expected follow-up Sprints:

- AI-ARCH-10 LightGBM Dataset Builder Preview
- AI-ARCH-11 Local AI Evaluation Dashboard Preview
- Local AI shadow inference runner
- Model Registry evaluation report integration

---

## 12. Safety / Privacy

Shadow Evaluation results must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- full raw OHLCV arrays
- raw Journal record dumps

Shadow Evaluation is not an order command.

`agreement_score` must not be used to bypass:

- Router
- Risk Guard
- Execution Layer

Even high agreement remains preview/shadow evaluation until a separate approved Goal connects it to another layer.

---

## 13. Prohibited Connections

This Sprint explicitly prohibits:

- Router auto connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- model training execution
- external AI provider calls
