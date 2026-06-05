# AITS LightGBM Dataset Builder Preview v1

Status: Dataset Builder Preview
Scope: Unified Trading Journal records to LightGBM feature/label rows

---

## 1. Purpose

The LightGBM Dataset Builder Preview converts Unified Trading Journal records into feature/label dataset rows for future Local AI ML Engine training and evaluation.

This Sprint only creates preview rows and exports them.

It does not train LightGBM.

It does not create model artifacts.

It does not connect to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 2. Dataset Builder Preview Definition

The builder reads Journal records from SQLite and creates:

- feature groups
- labels
- target candidates
- sample weight
- quality flags

The output is a dataset preview, not a trading signal.

---

## 3. Dataset Row Schema

Schema:

```text
aits_lightgbm_dataset_row.v1
```

Example:

```json
{
  "schema": "aits_lightgbm_dataset_row.v1",
  "row_id": "lgbm-row-lgbm-dataset-001",
  "source_journal_id": "lgbm-dataset-001",
  "created_at": "...",
  "symbol": "KRW-BTC",
  "timeframe": "5m",
  "provider": "openai",
  "engine_role": "preview",
  "features": {
    "market": {},
    "technical": {},
    "candidate": {},
    "portfolio": {},
    "ai_output": {},
    "router": {}
  },
  "labels": {},
  "targets": {},
  "sample_weight": 1.0,
  "quality": {
    "usable_for_training": false,
    "usable_for_inference_preview": true,
    "excluded_reason": null,
    "leakage_checked": true
  },
  "meta": {}
}
```

---

## 4. Feature Groups

### market

Source:

- `market_snapshot`
- top-level `timeframe`

Examples:

- `price_change_1m`
- `price_change_5m`
- `price_change_15m`
- `price_change_1h`
- `volatility_short`
- `volatility_mid`
- `volume_change`
- `trade_value_change`
- `spread_proxy`
- `market_regime`

### technical

Source:

- `basic_snapshot`

Examples:

- `rsi`
- `macd`
- `macd_signal`
- `macd_hist`
- `moving_average_short`
- `moving_average_mid`
- `moving_average_long`
- `ma_alignment`
- `breakout_score`
- `pullback_score`
- `overheat_score`

### candidate

Source:

- `basic_snapshot`
- `recommendation`

Examples:

- `basic_score`
- `candidate_rank`
- `candidate_reason_code`
- `is_rotation_candidate`
- `is_risk_candidate`
- `is_take_profit_candidate`
- `is_stop_loss_candidate`
- `basic_risk_level`

### portfolio

Source:

- `portfolio_context`
- `basic_snapshot.portfolio_context`

Examples:

- `holding_state`
- `position_size_ratio`
- `unrealized_pnl_pct`
- `holding_duration_minutes`
- `cash_ratio`
- `concentration_ratio`
- `max_position_limit_ratio`
- `asset_policy_risk_level`

### ai_output

Source:

- `provider`
- `engine_role`
- `ai_output_contract`

Examples:

- `ai_confidence`
- `ai_action`
- `ai_intent_type`
- `ai_eta_bucket`
- `ai_safety_level`
- `ai_reason_code`
- `teacher_signal_flag`

Full why/scenario objects are not copied into features.

### router

Source:

- `router_validation`
- `safety`
- `execution`

Examples:

- `router_allowed`
- `router_block_reason_code`
- `risk_guard_status`
- `validation_result`
- `final_action`
- `shadow_only`
- `preview_only`
- `executed`

---

## 5. Labels / Targets

Labels come from:

- `learning_label`
- `outcome`

Supported labels:

- `label_ready`
- `label_action_quality`
- `label_buy_quality`
- `label_sell_quality`
- `label_risk_quality`
- `label_rank_score`
- `label_pnl_bucket`

Targets:

- `ranker_target = label_rank_score`
- `classifier_target = label_action_quality or label_buy_quality`
- `regressor_target = outcome.expected_pnl_proxy or outcome.pnl_proxy`

Outcome-derived fields are labels/targets only.

They are not inference features.

---

## 6. Leakage Prevention

The builder excludes future/outcome/review-derived keys from feature groups.

Blocked key families:

- `pnl_after`
- `hit_take_profit`
- `hit_stop_loss`
- `max_drawdown_after`
- `max_runup_after`
- `opportunity_missed`
- `false_buy`
- `false_sell`
- `human_review_score`
- `future`
- `raw_future_candles`

Rules:

- outcome fields may be labels or targets
- outcome fields must not become features
- review fields must not become features
- raw future candles are prohibited
- raw Journal dumps are prohibited

---

## 7. Sample Weight

Default:

```text
1.0
```

Adjustments:

- executed record: `+0.3`
- shadow record: `+0.1`
- label ready: `+0.2`
- review present: `+0.2`
- outcome present: `+0.2`

Maximum:

```text
1.8
```

Sample weight is a preview hint. It is not a live trading signal.

---

## 8. JSONL Export

Helper:

```text
export_lightgbm_dataset_jsonl()
```

Rules:

- UTF-8
- one row per line
- `ensure_ascii=False`
- parent directory may be created
- sensitive and leakage-prone keys are removed during export

---

## 9. CSV Export

Helper:

```text
export_lightgbm_dataset_csv()
```

The CSV exporter flattens feature groups.

Column examples:

- `market__market_regime`
- `technical__rsi`
- `candidate__basic_score`
- `portfolio__holding_state`
- `ai_output__ai_action`
- `router__final_action`
- `label__label_action_quality`
- `target__classifier_target`
- `quality__usable_for_training`

No external dependency is required.

---

## 10. Current Disconnected State

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
- Local AI inference
- LightGBM training

---

## 11. Future Connections

Expected follow-up Sprints:

- AI-ARCH-11 Local AI Evaluation Dashboard Preview
- AI-ARCH-12 LightGBM Trainer Skeleton
- Model Registry evaluation report integration
- Dataset quality report preview

---

## 12. Safety / Privacy

Dataset rows must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- full raw OHLCV arrays
- raw future candles
- raw Journal record dumps

Dataset rows are learning candidates, not order commands.

LightGBM scores must not bypass:

- Router
- Risk Guard
- Execution Layer

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
- dependency changes
