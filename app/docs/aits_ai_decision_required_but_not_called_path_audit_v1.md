# AITS AI Decision Required But Not Called Path Audit v1

## 1. Audit Summary

This audit reviews the remaining Engine Role Contract guard finding:
`ai_decision_required_but_not_called_path_detected=true`.

The Buy Ready direct order path was already remediated by the AI Decision Gate and
AI response validator work. Current dry-read confirms:

- `basic_direct_buy_decision_detected=false`
- `order_intent_without_ai_decision_detected=false`
- `trigger_used_as_action_detected=false`
- `ai_response_validator_detected=true`
- `buy_ready_ai_gate_enabled=true`
- RiskGuard, LivePreflight, and execution bypass scans are false.

The remaining gap is not the Buy Ready path. It is concentrated in rotation,
managed-pool promotion, ETA/invalidation redecision, and provider runtime
escalation policy. These areas have planning, preview, or schema support, but
some AI-decision-required events still do not have a complete payload -> provider
call -> validated AI action path.

No trading, order, rotation, or execution logic was changed in this audit.

## 2. Current Harness Findings

Latest dry-read report:

- `status=pass`
- `engine_role_contract_guard_ready=true`
- `ai_decision_required_but_not_called_path_detected=true`
- `role_contract_violation_count=1`
- `role_contract_first_blocker=ai_decision_required_but_not_called_path_detected`
- `basic_direct_buy_decision_detected=false`
- `order_intent_without_ai_decision_detected=false`
- `trigger_used_as_action_detected=false`
- `ai_response_validator_detected=true`
- `riskguard_bypass_detected=false`
- `livepreflight_bypass_detected=false`
- `execution_bypass_detected=false`
- runtime-order truth hardcode scans are false.

## 3. Rotation AI Decision Gaps

### Current flow

Files and anchors:

- `app/services/managed_pool_promotion_policy.py`
  - `build_managed_pool_promotion_plan`
  - `_normalized_rotation_score`
- `app/ui/app_gui.py`
  - `_preview_managed_pool_rotation_plan`

The promotion policy computes `normalized_rotation_score` for the existing
managed row and the new scanner candidate. When the candidate score exceeds the
configured promotion score and margin, the plan includes a `planned_rotation`
entry with fields such as `old_symbol`, `new_symbol`, `score_gap`,
`rotation_allowed`, and `reason`.

The plan is explicitly preview-only:

- `observe_only=True`
- `managed_pool_mutation=False`
- `rotation_execution=False`
- `order_execution=False`

The UI preview writer logs `rotation_scan`, `rotation_plan_preview`, or
`rotation_plan_skipped`, and stores `_last_managed_pool_rotation_plan`.

### Gap

Rotation score is currently a planning signal. It does not mutate the Managed
Pool in the observed default path. However, a complete AI rotation decision path
is not yet present:

- no dedicated `task=rotation_decision` payload builder was found;
- no provider call is attached to a rotation candidate event;
- no validated `rotate` AI action is required before a future rotation apply;
- `rotate_to_symbol` exists in the generic AI output schema, but is not wired to
  the rotation preview plan as the final authority.

### Classification

`policy_gap`

This is not an immediate execution violation because current rotation is
observe-only. It becomes a high-priority fix before any managed-pool mutation,
rotation sell, or rotation buy apply stage is enabled.

## 4. Managed Pool Promotion AI Decision Gaps

### Current flow

Files and anchors:

- `app/ui/app_gui.py`
  - `_apply_managed_pool_max_size_sync`
  - `_collect_basic_candidates_for_managed_pool_sync`
  - `_build_basic_added_managed_pool_row`
- `app/services/managed_pool_promotion_policy.py`
  - `build_managed_pool_promotion_plan`
  - `build_managed_pool_quality_rebuild_plan`

The max-count apply path collects Basic scanner candidates, builds a quality
plan, and can create `basic_added` Managed Pool rows when the user confirms the
operation. This path keeps order execution disabled and protects holdings and
user-added rows.

### Gap

Managed Pool promotion is not a trade submit path, but it does change the
operational universe. Under the current role contract, Basic scores and quality
gates should be treated as candidate triggers, not final promotion authority.

Gaps found:

- no dedicated `task=managed_pool_promotion_decision` payload builder;
- no AI provider decision is required before Basic candidates become
  `basic_added` rows;
- max-count and quality-gate promotion can shape the managed universe without a
  validated AI action;
- user-added, live-holding, and external-holding rows are valid exceptions and
  should not require AI promotion.

### Classification

`likely_violation` for automatic/basic candidate promotion.

`false_positive` for user-added rows and live/external holding adoption, because
those are user or account-reconciliation facts rather than Basic market
judgments.

## 5. ETA / Invalidation Redecision Gaps

### Current flow

Files and anchors:

- `app/services/ai_engine_provider.py`
  - `validate_ai_decision_response`
  - `generate_position_management_decision`
  - `_parse_position_management_decision_response`
- `app/ui/app_gui.py`
  - `_build_ai_position_decision_payload`
  - `_request_ai_position_decision`
  - `_record_ai_position_decision_training`

The AI output contract includes `eta_seconds` and `invalidation_conditions`.
Training records persist the payload, AI action, confidence, reason, and
execution result placeholder fields.

### Gap

The audit did not find a dedicated runtime loop that:

- stores prior AI decisions as active redecision state;
- decrements or expires `eta_seconds`;
- evaluates `invalidation_conditions`;
- emits a new AI decision request when ETA expires or a condition is violated.

Current ETA appears to be primarily a displayed and recorded field, not a live
redecision trigger.

### Classification

`policy_gap`

This does not directly submit orders, but it means `wait` and `hold` decisions
can lack a reliable automatic re-evaluation path.

## 6. Sell / Take-Profit / Stop-Loss AI Decision Gaps

### Current flow

Files and anchors:

- `app/ui/app_gui.py`
  - `_evaluate_sell_takeprofit_observe_path`
  - `_build_ai_position_decision_payload`
  - `_request_ai_position_decision`
  - `_execute_ai_position_decision`
- `app/services/ai_engine_provider.py`
  - `validate_ai_decision_response`
  - `generate_position_management_decision`

The sell evaluation loop still observes PnL thresholds, but these thresholds now
create an AI decision requirement instead of directly determining final action.
When a candidate exists, the code logs `ai_decision_required`, builds a
`manage_position_decision` payload, requests the selected AI provider, and only
passes sell-like actions to guarded sell handling after the AI decision is
confirmed.

### Gap

No direct fixed-threshold sell execution path was found in the current audited
flow. Remaining issues are operational rather than role-contract violations:

- external providers can be blocked by runtime call gates;
- LOCAL AI may return `wait` unless its confidence logic escalates;
- ETA/invalidation redecision is not fully connected after hold/wait.

### Classification

`false_positive` for direct fixed-threshold sell.

`policy_gap` for post-decision re-evaluation and escalation.

## 7. Provider Runtime Call Gaps

### Current flow

Files and anchors:

- `app/services/ai_engine_provider.py`
  - `generate_position_management_decision`
  - `_call_openai_position_management_decision`
  - `_call_gemini_position_management_decision`
  - `_build_local_position_management_decision`
- `app/ui/app_gui.py`
  - `_selected_ai_decision_provider`
  - `_request_ai_buy_decision`
  - `_request_ai_position_decision`

Buy and position-management decisions now have provider-call entry points. LOCAL
decision generation is available. External provider calls are guarded by runtime
environment switches and return a blocked/wait decision when unavailable.

### Gap

Provider call support is not uniformly connected to every AI-decision-required
event:

- Buy Ready is connected.
- Sell/take-profit/stop-loss is connected.
- Rotation is not connected to a dedicated provider decision path.
- Managed Pool promotion is not connected to a dedicated provider decision path.
- ETA/invalidation redecision is not connected to a scheduler.
- LOCAL-first to GPT/GEMINI escalation is described by policy but not fully
  implemented as a runtime escalation chain.

### Classification

`policy_gap`

Provider-blocked cases are logged as blockers; the gap is missing provider-call
coverage for non-buy, non-position-management trigger categories.

## 8. Violation Table

| id | severity | category | file | function | anchor | description | current_flow | expected_flow | classification | recommended_fix_goal |
|---|---|---|---|---|---|---|---|---|---|---|
| AITS-AI-NOTCALLED-001 | MEDIUM | rotation | `app/services/managed_pool_promotion_policy.py` | `build_managed_pool_promotion_plan` | `planned_rotation` | Rotation plan is score-driven and preview-only, with no dedicated AI rotation payload/provider call. | normalized score creates preview plan; no mutation. | Rotation candidate should create `task=rotation_decision`; validated AI `rotate` action required before any apply. | policy_gap | `AITS-ROTATION-AI-DECISION-GATE-FIX` |
| AITS-AI-NOTCALLED-002 | HIGH | managed_pool_promotion | `app/ui/app_gui.py` | `_apply_managed_pool_max_size_sync` | `planned_add` -> `_build_basic_added_managed_pool_row` | Basic scanner candidates can become `basic_added` rows after user apply without AI promotion decision. | Basic quality gate creates managed rows; no order submit. | Basic candidate promotion should require AI promotion decision unless user-added or account-holding exception. | likely_violation | `AITS-MANAGED-POOL-PROMOTION-AI-GATE-FIX` |
| AITS-AI-NOTCALLED-003 | MEDIUM | eta_redecision | `app/services/ai_engine_provider.py` / `app/ui/app_gui.py` | validator and request/training paths | `eta_seconds`, `invalidation_conditions` | ETA and invalidation fields exist but are not owned by a live redecision scheduler. | Stored/displayed in decision records. | BASIC should monitor ETA and invalidation and trigger new AI payload when expired/violated. | policy_gap | `AITS-ETA-INVALIDATION-REDECISION-SCHEDULER-FIX` |
| AITS-AI-NOTCALLED-004 | LOW | sell_decision | `app/ui/app_gui.py` | `_evaluate_sell_takeprofit_observe_path` | `ai_decision_required` | Sell thresholds now trigger AI decision and no direct sell violation was found. | Trigger -> payload -> provider -> validated AI action. | Maintain as-is; extend ETA/escalation. | false_positive | none |
| AITS-AI-NOTCALLED-005 | MEDIUM | provider_runtime | `app/services/ai_engine_provider.py` | `generate_position_management_decision` | provider gates | External provider calls are guarded and not all trigger categories have provider call paths. | Buy/sell are connected; rotation/promotion/ETA are not. | All AI-required event categories should have provider request, blocker, and training record paths. | policy_gap | `AITS-AI-PROVIDER-RUNTIME-TRIGGER-COVERAGE-FIX` |
| AITS-AI-NOTCALLED-006 | MEDIUM | local_escalation | `app/services/ai_engine_provider.py` | `_build_local_position_management_decision` | LOCAL decision | LOCAL decision exists, but LOCAL-low-confidence escalation to external provider is not a complete runtime chain. | LOCAL may return wait/hold. | Low-confidence or high-risk LOCAL decisions should escalate when policy/provider permits. | policy_gap | `AITS-LOCAL-FIRST-GPT-GEMINI-ESCALATION-FIX` |

## 9. Fix Priority

1. `AITS-MANAGED-POOL-PROMOTION-AI-GATE-FIX`
   - Prevent Basic scanner quality gates from being final managed-pool promotion
     authority for `basic_added` rows.
2. `AITS-ROTATION-AI-DECISION-GATE-FIX`
   - Convert normalized rotation score from preview-only planning into
     `rotation_decision` payloads before any future apply path.
3. `AITS-ETA-INVALIDATION-REDECISION-SCHEDULER-FIX`
   - Make `eta_seconds` and `invalidation_conditions` active redecision
     triggers.
4. `AITS-AI-PROVIDER-RUNTIME-TRIGGER-COVERAGE-FIX`
   - Ensure each AI-required event category has provider call, provider blocked,
     and training-record coverage.
5. `AITS-LOCAL-FIRST-GPT-GEMINI-ESCALATION-FIX`
   - Implement LOCAL confidence/risk based escalation to external providers.

## 10. Recommended Next Goals

Recommended immediate next goal:

`AITS-MANAGED-POOL-PROMOTION-AI-GATE-FIX`

Reason: this is the only remaining audited path where Basic candidate scoring can
change AITS' managed operating universe without a dedicated AI decision. It does
not directly submit orders, but it affects future monitoring, rotation, and order
eligibility.

Recommended follow-up:

`AITS-ROTATION-AI-DECISION-GATE-FIX`

Reason: rotation is currently safely preview-only, but any future apply stage
must be guarded by an AI `rotate` decision before mutation or order routing is
enabled.

## 11. Managed Pool Promotion AI Gate Follow-Up

The `AITS-MANAGED-POOL-PROMOTION-AI-GATE-FIX` patch converts automatic Basic
scanner promotion from direct universe mutation into an AI-gated promotion
decision.

- Basic scanner candidates now become promotion triggers.
- Promotion payloads use `task=managed_pool_promotion_decision`.
- Valid promotion actions are `promote`, `reject`, `wait`, `replace`,
  `rotate_review`, and `hold`.
- AI-approved automatic rows carry promotion metadata and use
  `source_type=basic_added_ai_approved`.
- `user_added`, `live_holding`, and `external_holding` remain exception
  policies.
- Provider blocked, invalid schema, wait, hold, and reject outcomes block
  Managed Pool insertion and record a blocker.
- Promotion decision records are written for LOCAL training under
  `promotion_decisions.jsonl`.
