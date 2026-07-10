# AITS BASIC Direct Decision Path Audit v1

## 1. Audit Summary

This audit classifies the role-contract guard findings from dry-read after
`AITS-ENGINE-ROLE-CONTRACT-HARNESS-GUARD-03`.

Result:

- BASIC direct buy path: `likely_violation`
- OrderIntent without AI decision: `likely_violation` for the buy path, `false_positive` for sell preview samples
- Trigger-to-action: mixed; buy score to action is `likely_violation`, dust threshold samples are `false_positive`
- fixed threshold direct action: current guard reports false; sell thresholds route to AI decision request before sell apply
- actual-order hardcode finding: mostly `log_literal` and `runtime_logic`, not direct submit hardcode
- AI response validator: `partial_runtime_parser`, but central response validator is missing
- RiskGuard / LivePreflight / Execution bypass: not detected

No trading, order, router, guard, preflight, execution, or adapter logic was changed in this audit.

## 2. Current Harness Findings

Latest dry-read report:

| field | value | audit interpretation |
|---|---:|---|
| engine_role_contract_guard_ready | true | Guard is active. |
| basic_direct_buy_decision_detected | true | Buy Ready can enter live buy pipeline without AI decision payload. |
| basic_direct_sell_decision_detected | false | Sell path is currently AI-decision based. |
| basic_direct_rotation_decision_detected | false | Rotation remains observe-only. |
| order_intent_without_ai_decision_detected | true | Buy path is the main finding; sell sample is a blocked log. |
| trigger_used_as_action_detected | true | Mixed signal; buy score/status is meaningful, dust threshold samples are noise. |
| fixed_threshold_direct_action_detected | false | PnL thresholds trigger AI decision candidates, not direct submit. |
| ai_response_validator_detected | false | Parser exists, but no named central validator contract. |
| local_training_record_path_detected | true | Position decision records are stored. |
| riskguard_bypass_detected | false | No bypass found. |
| livepreflight_bypass_detected | false | No bypass found. |
| execution_bypass_detected | false | No bypass found. |
| direct_upbit_order_detected | false | No direct private order submit path found. |
| actual_order_hardcode_detected | true | Mostly post-submit reflection literals and actual trade row marking. |

## 3. BASIC Direct Buy Decision Paths

### Path BDD-01: CandidateFeed Buy Ready to live auto order pipeline

- file: `app/ui/app_gui.py`
- function: candidate feed score update / managed candidate evaluation block
- anchor: around `OrderIntentCandidate` log at line 42746
- source signal: managed row `ai_status == "Buy Ready"` and `_is_aits_pool_row_candidate_eligible(candidate_row)`
- AI payload before selection: none found
- AI provider call before selection: none found
- OrderIntent candidate log: yes
- RiskGuard location: after synthetic `AIDecisionState(action="buy")`
- LivePreflight location: after RiskGuard
- classification: `likely_violation`

Current flow:

`managed row score/status` -> `Buy Ready` -> first eligible candidate -> `OrderIntentCandidate` log -> `_run_live_auto_order_pipeline_from_candidate(...)`.

Expected flow:

`managed row score/status` -> AI decision trigger -> AI buy/add/hold decision payload -> AI response validator -> only AI `buy/add` action can create buy intent -> RiskGuard -> LivePreflight -> Execution.

Notes:

- The path does not bypass RiskGuard or LivePreflight.
- The issue is authority: BASIC score/status becomes a buy action candidate before AI decision authority.

### Path BDD-02: `_run_live_auto_order_pipeline_from_candidate`

- file: `app/ui/app_gui.py`
- function: `_run_live_auto_order_pipeline_from_candidate`
- anchor: line 56409
- source signal: `candidate_row`, `candidate_score`, `candidate_source`
- AI payload before Router: none found
- AI provider call before Router: none found
- Router input: synthetic `AIDecisionState(action="buy", confidence=score/100)`
- classification: `actual_violation_candidate`

Current flow:

`Buy Ready candidate` -> duplicate/cap/account/price checks -> synthetic `AIDecisionState(action="buy")` -> DecisionRouter -> RiskGuard -> LivePreflight -> ExecutionBridge -> OrderAdapter.

Expected flow:

`Buy Ready candidate` should become AI trigger and payload. BASIC should not synthesize a buy decision as if it were an AI final action.

## 4. OrderIntent Without AI Decision Paths

### Path OI-01: Buy OrderIntentCandidate

- file: `app/ui/app_gui.py`
- function: candidate feed score update / live order candidate block
- anchor: line 42746
- current fields: `side=buy`, `reason=buy_ready_candidate`, `router_called=False`, `riskguard_called=False`, `live_preflight_called=False`, `submitted=0`, `actual_order=False`
- classification: `likely_violation`

This line is a candidate log, not a submit. It is still a role-contract concern because the candidate exists before AI decision payload or AI action id.

### Path OI-02: Router handoff preview

- file: `app/ui/app_gui.py`
- function: same candidate block
- anchor: around line 42836
- current fields: `observe_only=True`, `router_apply=False`, `final_action_applied=False`, `submitted=0`, `actual_order=False`
- classification: `false_positive_for_submit`, `useful_signal_for_contract_gap`

This is an observe-only preview. It confirms the system already has a no-apply preview vocabulary, but the live buy path still has a separate apply path.

### Path OI-03: SellOrderIntent blocked sample

- file: `app/ui/app_gui.py`
- function: `_execute_ai_position_decision`
- anchor: around line 40333
- current fields: sell intent blocked, AI action included, no submit
- classification: `false_positive`

This is not an AI-less sell intent. It is a blocked log inside the AI-decision sell execution coordinator.

## 5. Trigger-to-Action Paths

### Path TA-01: Buy Ready as action trigger

- file: `app/ui/app_gui.py`
- function: candidate feed score update / live order candidate block
- anchor: around lines 42700-42880
- trigger: `Buy Ready`, score threshold, candidate eligibility
- action conversion: buy candidate enters live auto order pipeline
- classification: `likely_violation`

The trigger should become `ai_decision_required`, not direct buy pipeline input.

### Path TA-02: Take-profit / stop-loss thresholds

- file: `app/ui/app_gui.py`
- function: sell evaluation observe/apply candidate builder
- anchor: around lines 40695-40759
- trigger: PnL thresholds
- action conversion: thresholds build AI decision candidates, then `_request_ai_position_decision(...)`
- classification: `not_violation_currently`

Current sell thresholds are not direct submit conditions. They create AI decision candidates and route through AI decision authority before sell apply.

### Path TA-03: Dust threshold samples

- file: `app/ui/app_gui.py`
- function: managed holding dust classification
- anchors: around lines 18555-18567
- classification: `false_positive`

Dust thresholds classify manageability, not buy/sell/rotate action.

### Path TA-04: Rotation score

- file: `app/services/managed_pool_promotion_policy.py`
- function: rotation plan builder
- anchors: `_normalized_rotation_score`, `planned_rotation`
- classification: `not_live_action`, `future_ai_integration_needed`

Rotation score creates observe-only plans with `managed_pool_mutation` false. It is not currently a live mutation, but future rotation apply must require AI decision authority.

## 6. actual_order Hardcode Classification

### Finding AO-01: TradeLog reflection log literals

- file: `app/ui/app_gui.py`
- function: `_reflect_live_order_trade_log`
- anchors: around lines 30967, 30982, 31035, 31039, 31044
- classification: `log_literal`

These are log strings marking reflection after a submitted live order. They do not place orders.

### Finding AO-02: actual trade row marking

- file: `app/ui/app_gui.py`
- function: `_reflect_live_order_trade_log`
- anchor: row field `actual_order` set to true after post-submit reflection
- classification: `runtime_logic`

This is not submit hardcoding. It records an actual trade row only after the caller passes `submitted_count > 0` via `_reflect_live_order_after_submit(...)`.

Risk:

- LOW to MEDIUM audit ambiguity. The value is legitimate as post-submit reflection, but the guard cannot yet distinguish post-submit reflection from unsafe hardcode.

Recommended guard improvement:

- Reclassify this pattern as safe only when inside `_reflect_live_order_trade_log` and gated by a caller path that checks `submitted_count > 0`.

### Finding AO-03: submitted count samples

- file: `app/ui/app_gui.py`
- anchors: lines 25267, 25269, 40577 and similar
- classification: `runtime_counter_or_log_literal`

These are count coercions or display mappings. They are not direct submit fabrication by themselves.

## 7. AI Response Validator Status

### Current state

- file: `app/services/ai_engine_provider.py`
- function: `_parse_position_management_decision_response`
- status: partial parser and normalization exists

Detected behavior:

- JSON parse with fallback extraction.
- Allowed action set fallback to `wait`.
- Confidence clamped to 0.0-1.0.
- ETA parsed with default.
- Sell ratio clamped to 0.0-1.0.
- Empty reason forces `wait`.
- Output includes `invalidation_conditions`.

Missing contract:

- No named central validator such as `validate_ai_position_decision_response`.
- No explicit required-field result object.
- No explicit validation status/blocker taxonomy for missing `reason_ko`, invalid `eta_seconds`, invalid `rotate_to_symbol`, invalid `buy_amount_krw`, invalid `execution_plan`, or non-list `invalidation_conditions`.
- No shared validator used by buy, sell, add, reduce, and rotate.

Classification: `actual_gap`, severity `MEDIUM`.

## 8. RiskGuard/LivePreflight/Execution Bypass Status

No bypass was found in the audited live buy path.

Observed guarded flow in `_run_live_auto_order_pipeline_from_candidate`:

1. DecisionRouter route
2. RiskGuard `evaluate_order_candidate`
3. LiveOrderPreflight `evaluate`
4. ExecutionBridge `build_live_guarded_window_bridge`
5. AITSOrderAdapter `execute`

Bypass fields:

| field | result |
|---|---:|
| riskguard_bypass_detected | false |
| livepreflight_bypass_detected | false |
| execution_bypass_detected | false |
| direct_upbit_order_detected | false |

## 9. Violation Table

| id | severity | category | file | function | anchor | description | current_flow | expected_flow | classification | recommended_fix_goal |
|---|---|---|---|---|---|---|---|---|---|---|
| BDD-01 | HIGH | BASIC direct buy | `app/ui/app_gui.py` | candidate feed score update block | `OrderIntentCandidate`, line 42746 | Buy Ready can create buy candidate before AI decision. | score/status -> Buy Ready -> candidate | trigger -> AI payload -> AI action -> intent | likely_violation | AI buy decision payload gate |
| BDD-02 | HIGH | BASIC synthetic buy decision | `app/ui/app_gui.py` | `_run_live_auto_order_pipeline_from_candidate` | line 56409 | BASIC builds `AIDecisionState(action="buy")`. | Buy Ready -> synthetic buy decision -> Router | AI decision response -> Router | actual_violation_candidate | Replace synthetic buy action with AI decision authority |
| OI-01 | HIGH | AI-less intent | `app/ui/app_gui.py` | candidate feed score update block | line 42746 | Buy candidate lacks ai_decision_id/payload_hash/provider action. | candidate log before AI decision | AI decision metadata required before intent | likely_violation | OrderIntent AI metadata contract |
| TA-01 | HIGH | Trigger to action | `app/ui/app_gui.py` | candidate feed score update block | lines 42700-42880 | Buy Ready trigger can feed apply path. | trigger -> live pipeline | trigger -> AI decision required | likely_violation | Trigger-to-AI gate |
| TA-02 | FALSE_POSITIVE | Sell threshold | `app/ui/app_gui.py` | SellEvaluation | lines 40695-40759 | PnL threshold samples are AI triggers, not direct submit. | threshold -> AI candidate | acceptable | false_positive | none |
| TA-03 | FALSE_POSITIVE | Dust threshold | `app/ui/app_gui.py` | dust classification | lines 18555-18567 | Dust threshold is manageability classification. | threshold -> dust exclude | acceptable | false_positive | tune harness sample filters |
| AO-01 | LOW | actual-order literal | `app/ui/app_gui.py` | `_reflect_live_order_trade_log` | lines 30967-31044 | Log literals use actual-order true after submit reflection. | post-submit reflection log | acceptable with gate | log_literal | refine guard classification |
| AO-02 | MEDIUM | actual trade row marker | `app/ui/app_gui.py` | `_reflect_live_order_trade_log` | actual trade row append | Row marks actual trade after submitted order result. | submitted_count -> actual trade row | acceptable with explicit gate | runtime_logic | document safe post-submit marker |
| VAL-01 | MEDIUM | AI validator missing | `app/services/ai_engine_provider.py` | `_parse_position_management_decision_response` | parse function | Parser exists, central validator absent. | parse/normalize inline | shared validator contract | actual_gap | AI response validator contract |
| ROT-01 | LOW | rotation AI integration | `app/services/managed_pool_promotion_policy.py` | rotation plan builder | planned_rotation | Observe-only rotation is not live mutation. | normalized score -> preview | future AI decision before apply | future_gap | rotation AI decision integration |

## 10. Fix Priority

1. AI response validator missing.
   - Add a named validator contract for AI position decisions.
   - Return validation status, blockers, normalized action, and safe defaults.
2. Buy Ready direct OrderIntent path.
   - Convert Buy Ready into AI decision trigger and payload.
   - Require AI action `buy` or `add` before live buy intent.
3. Trigger-to-action guard.
   - Ensure trigger outputs never call apply paths without AI decision metadata.
4. actual-order guard refinement.
   - Teach harness to classify post-submit reflection literals separately from unsafe runtime hardcode.
5. Rotation AI decision integration.
   - Keep observe-only for now; require AI action before future mutation.

## 11. Recommended Next Goals

1. `AITS-AI-RESPONSE-VALIDATOR-CONTRACT-AND-HARNESS-REFINE-01`
2. `AITS-BUY-READY-TO-AI-DECISION-PAYLOAD-GATE-01`
3. `AITS-ORDERINTENT-AI-METADATA-REQUIRED-CONTRACT-01`
4. `AITS-ACTUAL-ORDER-POST-SUBMIT-REFLECTION-GUARD-REFINE-01`
5. `AITS-ROTATION-AI-DECISION-AUTHORITY-INTEGRATION-01`
