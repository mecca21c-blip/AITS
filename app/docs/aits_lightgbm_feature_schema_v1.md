# AITS LightGBM Feature Schema v1

Status: Current LightGBM Feature Schema Definition
Scope: Journal-to-feature contract for Local AI ML Engine training, evaluation, and inference

---

## 1. Document Purpose

This document defines how Unified Trading Journal records are transformed into LightGBM input features.

It is the SSOT for the Local AI ML Engine's training, evaluation, and inference feature contract.

It prepares the input contract for future:

- Journal SQLite
- Journal Writer Preview
- GPT/Gemini Distillation Sample Builder
- Local AI Shadow Evaluator
- LightGBM Dataset Builder Preview

---

## 2. Feature Schema Philosophy

LightGBM is one ML Engine inside Local AI.

LightGBM does not replace the Reason Runtime.

LightGBM provides:

- Probability
- Score
- Ranking
- Risk estimate
- Performance proxy

Final explanation, intent, and narrative are handled by the Reason Runtime or AI Output Contract.

LightGBM results must not be displayed directly as AI Narrative.

LightGBM must not bypass:

- Router
- Risk Guard
- Execution Layer

LightGBM output is a preview/recommendation support signal, not a direct order command.

---

## 3. Schema Top-Level Structure

```json
{
  "schema": "aits_lightgbm_feature_schema.v1",
  "feature_schema_id": "...",
  "schema_name": "...",
  "schema_version": "1.0.0",
  "created_at": "...",
  "updated_at": "...",
  "source_schema": "aits_unified_trading_journal.v1",
  "target_model_types": [],
  "feature_groups": {},
  "label_schema": {},
  "target_definitions": {},
  "leakage_rules": {},
  "normalization_policy": {},
  "missing_value_policy": {},
  "train_inference_contract": {},
  "safety": {},
  "meta": {}
}
```

---

## 4. Target Model Types

Supported target model types:

- lightgbm_ranker
- lightgbm_classifier
- lightgbm_regressor

Roles:

- `lightgbm_ranker`: ranks candidate assets by priority.
- `lightgbm_classifier`: assists buy/reduce/hold/avoid style candidate classification.
- `lightgbm_regressor`: predicts continuous proxies such as pnl_proxy, risk_proxy, or opportunity_score.

These values are not direct order commands.

They are preview/recommendation support indicators.

---

## 5. Feature Groups

### A. market_features

- timeframe
- price_change_1m
- price_change_5m
- price_change_15m
- price_change_1h
- volatility_short
- volatility_mid
- volume_change
- trade_value_change
- spread_proxy
- market_regime

### B. technical_features

- rsi
- macd
- macd_signal
- macd_hist
- moving_average_short
- moving_average_mid
- moving_average_long
- ma_alignment
- breakout_score
- pullback_score
- overheat_score

### C. candidate_features

- basic_score
- candidate_rank
- candidate_reason_code
- is_rotation_candidate
- is_risk_candidate
- is_take_profit_candidate
- is_stop_loss_candidate
- basic_risk_level

### D. portfolio_features

- holding_state
- position_size_ratio
- unrealized_pnl_pct
- holding_duration_minutes
- cash_ratio
- concentration_ratio
- max_position_limit_ratio
- asset_policy_risk_level

### E. ai_output_features

These features are for learning and evaluation only when they are available at the correct time.

The schema must explicitly separate whether each AI output field is available at inference time.

- provider
- engine_role
- ai_confidence
- ai_action
- ai_intent_type
- ai_eta_bucket
- ai_safety_level
- ai_reason_code
- teacher_signal_flag

### F. router_features

- router_allowed
- router_block_reason_code
- risk_guard_status
- validation_result
- final_action
- shadow_only
- preview_only

### G. outcome_features

Outcome features are label-generation fields.

They are prohibited as inference input.

- pnl_after_10m
- pnl_after_30m
- pnl_after_60m
- pnl_after_1d
- max_drawdown_after_signal
- max_runup_after_signal
- hit_take_profit
- hit_stop_loss
- opportunity_missed
- false_buy
- false_sell

### H. review_features

Review features may be used for labels or sample weights.

Future-result-derived review features are prohibited as real-time inference input.

- review_result
- human_review_score
- ai_review_score
- error_type
- lesson_code
- label_ready

---

## 6. Label Schema

Candidate labels:

### label_action_quality

- good
- neutral
- bad

### label_buy_quality

- true_buy
- false_buy
- missed_buy
- no_buy

### label_sell_quality

- true_sell
- false_sell
- missed_sell
- no_sell

### label_risk_quality

- safe
- risky
- blocked_correctly
- blocked_incorrectly

### label_rank_score

Range:

- 0.0 to 1.0

### label_pnl_bucket

- loss_large
- loss_small
- flat
- profit_small
- profit_large

Training rules:

- Only records with `label_ready=true` are used for supervised learning.
- Records without outcome are excluded from supervised learning.
- Records without review may receive lower weight or be excluded.
- Shadow/preview records and executed records must be evaluated separately.

---

## 7. Target Definitions

### A. Ranker Target

Targets:

- candidate ranking quality
- opportunity score
- future relative performance

### B. Classifier Target

Targets:

- buy_candidate_quality
- reduce_candidate_quality
- avoid_risk_quality

### C. Regressor Target

Targets:

- expected_pnl_proxy
- expected_drawdown_proxy
- opportunity_cost_proxy

Important:

Targets are generated from future outcomes.

Outcome-related features must not be used at inference time.

---

## 8. Data Leakage Prevention Rules

The following rules are mandatory:

- `outcome_features` are for label generation and must not be inference input.
- Future-result-derived `review_features` must not be inference input.
- Values known only after execution result must not be inference features.
- `pnl_after_*` fields must not be input features.
- `hit_take_profit` and `hit_stop_loss` must not be input features.
- `human_review_score` is for training/evaluation and must not be real-time inference input.
- Raw future candles must not be stored as features or passed as inputs.
- Train/inference feature parity must be verified.
- Any feature with future knowledge must be blocked from inference vectors.

---

## 9. Train / Inference Contract

### Train Time

Training pipeline:

1. Extract features from Journal records.
2. Confirm `label_ready=true`.
3. Confirm outcome exists for targets with `outcome_required=true`.
4. Apply leakage filter.
5. Generate `train_feature_vector`.
6. Generate label.
7. Compute sample weight.

### Inference Time

Inference pipeline:

1. Use only current market/basic/portfolio/router preview information.
2. Do not use outcome, review, or future values.
3. Generate `inference_feature_vector`.
4. Keep column order identical to the train schema.
5. Apply missing value policy.
6. Output prediction score.

Inference output is not a direct order command.

---

## 10. Missing Value Policy

Missing values must be recorded in the feature schema.

Policy:

- Numeric missing: null or explicit sentinel, defined per feature.
- Categorical missing: `unknown`.
- Boolean missing: false or null, defined per feature.
- Unavailable provider output: `not_available`.
- Unavailable portfolio state: `not_holding`.

The policy must be stable between train and inference.

---

## 11. Normalization / Encoding Policy

The schema must define:

- Numeric scaling policy
- Categorical encoding policy
- Boolean encoding policy
- Timeframe encoding policy
- Provider/action/reason_code encoding policy
- Whether LightGBM native categorical support is used

Encoding must remain compatible with registered model artifacts.

---

## 12. Sample Weight Policy

Suggested priority:

```text
executed record > shadow record > preview record
```

Weighting rules:

- Human-reviewed records may receive increased weight.
- High-confidence wrong records may receive high learning value as error-note samples.
- Noisy or insufficient-outcome records receive lower weight.
- Market-regime imbalance may be corrected with sample weighting.

---

## 13. Feature Versioning

Feature schema metadata:

- feature_schema_id
- schema_version
- compatible_model_ids
- deprecated_features
- added_features
- breaking_change

`feature_schema_id` must connect to the Local AI Model Registry.

Breaking schema changes require new model training or explicit compatibility validation.

---

## 14. Relationship With AI-ARCH-03 / AI-ARCH-04

Unified Trading Journal is the source record.

LightGBM Feature Schema is the contract that converts Journal records into feature vectors.

Local AI Model Registry tracks models trained with this Feature Schema.

Official flow:

```text
Journal -> Feature Schema -> Dataset -> Model Registry -> Evaluation
```

---

## 15. Safety / Governance

Rules:

- Do not store API keys.
- Do not store account secrets.
- Do not store raw private account detail.
- Do not store full raw OHLCV history in feature records.
- Do not force labels on records without outcomes.
- Do not automatically apply training results to live trading.
- Do not use model scores directly as order signals.
- Do not bypass Router, Risk Guard, or Execution.
- Keep preview, shadow, recommendation, and executed records separated.

---

## 16. Future Connected Sprints

AI-ARCH-06:

Journal SQLite Skeleton

AI-ARCH-07:

Journal Writer Preview

AI-ARCH-08:

GPT/Gemini Distillation Sample Builder

AI-ARCH-09:

Local AI Shadow Evaluator

AI-ARCH-10:

LightGBM Dataset Builder Preview
