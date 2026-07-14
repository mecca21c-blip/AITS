# AITS LOCAL Model Live Integration v1

## Purpose

This contract connects a trained LOCAL model to the AI provider router without granting it order ownership. BASIC builds factual payloads, existing LOCAL evaluates first, and LOCAL_MODEL may add a model-backed decision candidate.

## Registry Contract

- `latest_model.json` is the live policy source for the latest trained artifact.
- A model is loadable only when `trained=true`, its artifact remains below `data/local_models`, and `model.pkl` exists.
- `safe_for_live_decision` and `live_decision_enabled` are registry-owned approvals. Training defaults both to false.
- No code path may infer or force either approval flag.
- Missing, untrained, incompatible, or disabled models preserve the existing LOCAL and external-provider route.

## Provider Route

1. BASIC supplies the current factual payload and feature manifest.
2. Existing LOCAL produces the first AI decision.
3. LOCAL_MODEL converts factual payload fields into `aits_local_training_feature_record.v1` features and evaluates the trained artifact.
4. The escalation policy compares LOCAL and LOCAL_MODEL actions. A model order action requests external confirmation.
5. OpenAI or Gemini is called only through the existing cost guard.
6. A model decision can become the final provider source only when both registry approvals are true, feature quality is sufficient, the candidate passes the AI validator, and the candidate satisfies the router policy.
7. RiskGuard and LivePreflight remain mandatory for every later order-capable final action.

## Prediction Contract

- The action label comes from a classifier trained only on observed curated labels.
- Action quality, provider value, and risk scores come from trained targets. Missing targets make prediction unavailable.
- Confidence is derived from observed action-quality and risk scores, multiplied by the payload-quality factor. It is not a stored or fabricated constant.
- Critical feature gaps or D/F payload quality block prediction.
- LOCAL_MODEL never creates an OrderIntent and never calls Router, ExecutionBridge, OrderService, or OrderAdapter.

## Observation And Learning

Decision records retain model id, action, confidence, risk score, comparison with LOCAL/external/final decisions, live eligibility, non-use reason, and pending outcome linkage. Missing models are recorded as unavailable, not replaced with synthetic predictions.

## User Visibility

LIVE LOG and the shared status summary explain whether the trained model was unavailable, evaluated as reference-only, or selected under registry approval. Internal blocker names are not rendered as user-facing text.

## Completion

`local-model-live-integration-v1-summary --observe-only` checks registry state, prediction contracts, provider routing, safety ownership, training observation fields, UI copy, and compatibility with the previous model-training, LOCAL-first, and live-cycle summaries.
