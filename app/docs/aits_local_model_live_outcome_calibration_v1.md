# AITS LOCAL Model Live Outcome Calibration v1

## Purpose

This contract calibrates LOCAL_MODEL confidence and provider-routing recommendations from observed live decision outcomes. It does not grant trading authority, change a final action, or relax RiskGuard and LivePreflight.

## Sources

Calibration reads the decision outcome, provider comparison, curated training, feature, model registry, latest model, and latest metrics stores. Records require a decision id, an observed LOCAL_MODEL prediction, confidence, a usable outcome, and an approved training-quality source. Submitted orders additionally require reconciliation evidence. Corrupted, duplicated, unresolved valuation, synthetic, manual, or forced records are excluded.

An empty source is a valid state. It writes a no-data profile without predictions, outcomes, metrics, or thresholds fabricated by the calibration layer.

## Matching And Analysis

- Prediction and outcome matching is keyed by decision id and retains model, session, task, scope, and symbol provenance.
- Confidence is summarized in fixed buckets: 0-0.3, 0.3-0.5, 0.5-0.7, 0.7-0.85, and 0.85-1.0.
- A recommended confidence threshold requires at least 30 usable records and at least 10 records in a qualifying bucket.
- Action and task reliability require at least 10 records per group. Smaller groups remain `insufficient_sample`.
- Risk-score agreement is calibration evidence only and never replaces a runtime guard.

## Routing Recommendation

The profile may recommend calibrated wait/hold or portfolio groups as future LOCAL_MODEL final candidates. Buy, add, sell, reduce, take-profit, stop-loss, and rotation groups retain external confirmation until sufficient calibrated evidence and separate user approval exist.

The provider router loads profile metadata and records the recommendation. In v1, `local_model_calibration_applied_to_final_policy` is always false. Existing registry approvals and provider-routing logic remain the only LOCAL_MODEL activation controls.

## Profile Contract

Runtime data is written under `data/local_models`:

- `calibration_profile.json`
- `calibration_history.jsonl`
- `latest_calibration_summary.json`

The profile schema is `aits_local_model_calibration_profile.v1`. `safe_for_policy_use` permits reading conservative recommendations. `safe_for_live_expansion` remains false until at least 100 usable records, a real confidence threshold, and no observed unsafe model prediction are present. Even then, expansion requires a separate user-approved Goal.

## Safety

Calibration never creates an AI action, OrderIntent, order result, outcome, prediction, confidence, or model artifact. It has no dependency on DecisionRouter, ExecutionBridge, OrderService, or OrderAdapter. RiskGuard and LivePreflight remain mandatory.

## Visibility And Verification

LIVE LOG and the shared status summary explain no-data, insufficient-data, and profile-written states in Korean. Internal calibration keys are not rendered directly.

`local-model-live-outcome-calibration-v1-summary --observe-only` verifies source loading, matching, calibration analysis, profile files, recommendation-only router metadata, safety boundaries, and compatibility with prior LOCAL_MODEL and live-cycle contracts.
