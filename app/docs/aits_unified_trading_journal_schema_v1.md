# AITS Unified Trading Journal Schema v1

Status: Current Journal Schema Definition
Scope: Shared record schema for GPT, Gemini, Local AI, Basic Preview, Router, Execution, Review, and Learning

---

## 1. Journal Definition

The Unified Trading Journal is AITS' official judgement, outcome, and learning data store.

GPT, Gemini, Local AI, Router, Execution, and the Review System connect through this Journal.

---

## 2. Storage Purpose

The Journal stores:

- AI judgement records
- Basic calculation snapshots
- Execution or non-execution state
- Outcomes
- Success/failure review
- Local AI learning data
- GPT/Gemini knowledge distillation data
- Policy improvement history

---

## 3. Storage Media

Initial storage:

- SQLite

Optional exports:

- JSONL export
- CSV export

---

## 4. Journal Record Top-Level Structure

```json
{
  "schema": "aits_unified_trading_journal.v1",
  "journal_id": "...",
  "created_at": "...",
  "session_id": "...",
  "symbol": "KRW-BTC",
  "asset_name": "BTC",
  "timeframe": "1m/5m/15m/1h/4h/1d",
  "provider": "openai/gemini/local_ai/basic_preview",
  "engine_role": "preview/recommendation/validated/executed/review",
  "market_snapshot": {},
  "basic_snapshot": {},
  "ai_input_contract": {},
  "ai_output_contract": {},
  "recommendation": {},
  "router_validation": {},
  "execution": {},
  "outcome": {},
  "review": {},
  "learning_label": {},
  "safety": {},
  "meta": {}
}
```

---

## 5. market_snapshot

Market snapshot stores compact market context.

Fields:

- current_price
- price_change_pct
- volume
- volume_ratio
- high
- low
- spread
- orderbook_summary, optional

Important:

Do not store full raw OHLCV history in each record.

Use compact summary snapshots.

---

## 6. basic_snapshot

`basic_snapshot` stores Basic Engine output.

Fields:

- rsi
- macd
- ma20
- ma60
- ma120
- trend_score
- volume_score
- volatility_score
- risk_score
- candidate_type
- basic_reason_codes

Important:

The Basic Engine is not the judgement maker.

`basic_snapshot` is a fact, candidate, and risk record.

---

## 7. ai_input_contract

`ai_input_contract` stores compact context passed to GPT, Gemini, or Local AI.

Fields:

- asset
- technical_state
- risk_state
- portfolio_state
- policy_state
- recent_context
- requested_output
- safety_constraints

Prohibited:

- API keys
- Account secrets
- Raw logs
- Unbounded payload dumps

---

## 8. ai_output_contract

`ai_output_contract` stores AI-generated output.

Fields:

- intent
- scenario
- why
- eta
- confidence
- recommendation candidate

Important:

Do not store AI judgement without an AI Output Contract.

---

## 9. recommendation

`recommendation` is reserved for future P16-D5 and later recommendation work.

Fields:

- action_candidate
- allowed_actions
- position_intent
- allocation_hint
- rotation_hint
- stop_loss_hint
- take_profit_hint
- confidence
- reason_summary

Allowed `action_candidate` values:

- observe
- buy_candidate
- sell_candidate
- reduce_candidate
- rotate_candidate
- take_profit_candidate
- stop_loss_candidate

These are candidates, not direct order commands.

---

## 10. router_validation

`router_validation` stores Router validation results.

Fields:

- router_version
- accepted
- rejected_reason
- risk_guard_status
- policy_check
- fund_check
- final_action

Router validation does not erase the original AI or Basic snapshots.

---

## 11. execution

`execution` stores actual execution or non-execution state.

Fields:

- execution_mode
- submitted
- order_id
- order_type
- amount
- price
- simulated
- real_order

Current safety baseline:

- submitted=0
- real_order=false

---

## 12. outcome

`outcome` stores post-horizon result data.

Fields:

- evaluated_at
- horizon
- pnl_pct
- pnl_amount
- max_drawdown
- max_favorable_excursion
- success
- failure_reason

---

## 13. review

`review` stores AI Review System notes.

Fields:

- what_happened
- why_right
- why_wrong
- missed_signal
- improvement_note
- should_repeat
- should_avoid

---

## 14. learning_label

`learning_label` stores Local AI training labels.

Fields:

- label_ready
- target
- target_value
- class_label
- regression_label
- sample_weight
- exclude_from_training
- exclusion_reason

Allowed `class_label` values:

- success
- failure
- neutral
- unknown

---

## 15. safety

`safety` stores safety context.

Fields:

- preview_only
- shadow_only
- dry_run
- no_order_execution
- risk_guard_bypassed=false
- source_verified

---

## 16. meta

`meta` stores operational metadata.

Fields:

- app_version
- commit_hash
- data_quality
- missing_fields
- notes

---

## 17. Storage Principles

Records are append-only by default.

Existing record updates are allowed only for limited outcome/review enrichment.

Rules:

- Do not store API keys.
- Minimize personal/account-sensitive information.
- Keep Basic Preview and AI Output separated.
- `provider=basic_preview` is not AI judgement.
- Do not store full raw OHLCV data in each record.
- Do not store unbounded payloads.

---

## 18. Local AI Learning Principles

Only records with `learning_label.label_ready=true` are used for training.

Records without outcome are excluded from supervised learning.

GPT/Gemini records may be used as teacher signals.

Local AI records may be used as student signals.

Feature schema must be fixed before training.

---

## 19. Future DB Table Candidates

Document-level candidates:

- trading_journal
- journal_outcomes
- journal_reviews
- learning_samples
- model_versions

---

## 20. Prohibited Directions

Do not record API keys.

Do not record raw order secrets.

Do not store full raw OHLCV history in each record.

Do not store Basic calculation output as AI judgement.

Do not store a preview that was not executed as executed.

Do not mix real trading records with shadow records.

---

## 21. Future Sprints

AI-ARCH-04:

Local AI Model Registry

AI-ARCH-05:

LightGBM Feature Schema

AI-ARCH-06:

Journal SQLite Skeleton

AI-ARCH-07:

Journal Writer Preview

AI-ARCH-08:

GPT/Gemini Distillation Sample Builder
