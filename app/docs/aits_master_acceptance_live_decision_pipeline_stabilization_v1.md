# AITS Master Acceptance Live Decision Pipeline Stabilization V1

## Scope

This stabilization closes the source defect behind `MA-20260718-006` without changing trading, routing, guard, authority, or execution policy. Packaged Live acceptance remains pending explicit user approval.

## Root cause

`AIEngineProvider.generate_position_management_decision()` resolved the effective policy into its local `effective_policy` value, then called `_route_local_first_decision()` without passing that value. After a valid OpenAI response and validator PASS, `_route_local_first_decision()` referenced the undefined name while building the canonical Intent. Python compilation could not detect the runtime local-name error, and the earlier observe-only summaries did not execute this exact post-validator branch.

The failing call chain was:

1. `MainWindow._request_initial_ai_management_decision`
2. `AIEngineProvider.generate_position_management_decision`
3. `AIEngineProvider._route_local_first_decision`
4. `AITSAIIntentService.build(effective_policy=effective_policy)`

The broad GUI boundary converted the exception to `initial_seed_response_missing:NameError`, so the traceback was not retained. The boundary now records exception evidence while preserving the safe failure response.

## Stabilized contract

`aits_validated_decision_application.v1` records the deterministic post-validator application state:

- validated decision identity and provider provenance;
- Effective Policy identity;
- canonical Intent identity;
- runtime decision, ETA, invalidation, and outcome-tracking registration;
- unchanged final action;
- `actual_order=false` and `submitted=0`.

UI timeline rendering is isolated from core registration. A UI writer failure is recorded as a warning and cannot erase a completed core application result.

## Regression

`validated-decision-postprocess-regression-v1-summary` replays factual metadata from an existing external-provider, validator-passed, non-order HOLD decision in `data/ai_decision_training/position_decisions.jsonl`. It does not call a provider, synthesize an action, create an order, or mutate runtime source data.

The regression checks policy/decision/Intent identity, runtime decision registration, ETA and invalidation registration, outcome tracking, UI-writer isolation, final-action immutability, and zero order/submission/mutation counts.

## Acceptance state

After source regression PASS, `MA-20260718-006` may advance only to `acceptance_retest_required`. It must not be closed until RC4 packaged Live produces a valid external response and proves the full post-validator registration path. RC4 Live requires the explicit user phrase `Master Acceptance Live 재개`.
