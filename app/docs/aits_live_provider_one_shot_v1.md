# AITS Live Provider One-shot Safety Layer v1

## 1. Purpose

AITS Live Provider One-shot is a research and diagnostics layer for checking provider readiness before any production trading path is considered.

It verifies:
- provider connection readiness
- model configuration readiness
- key presence without exposing keys
- dry-run one-shot behavior
- live allow safety gate behavior

This is not a real trading integration.

## 2. Safety Contract

The one-shot layer must always preserve:
- `shadow_only=True`
- `one_shot=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`

It must never call:
- OrderAdapter
- ExecutionBridge
- Upbit order API
- automatic loops
- background cycles
- multi-provider auto-run

## 3. Provider Runtime Validator

`ProviderRuntimeValidator` validates runtime status without making a provider request.

It checks:
- provider availability
- key presence
- model presence
- local runtime readiness metadata
- dry-run support
- live one-shot support

Keys are never logged or returned.

## 4. Provider Capability Matrix

`ProviderCapabilityMatrix` defines static attach-only provider capabilities:
- dry_run
- live_one_shot
- local_runtime
- structured_json
- long_context
- vision
- research_mode

Capabilities are diagnostic metadata only and must not affect final trading action or confidence.

## 5. One-shot Report Builder

`ProviderOneShotReportBuilder` converts a one-shot result into a compact report:
- provider
- parsed validity
- next action
- scenario
- ETA
- state
- reliability hint
- summary line

The report is display/research data only.

## 6. Harness Safety Gate

`LiveProviderOneShotHarness` uses the runtime validator before any live-capable call.

If `allow_live=True` but runtime validation fails, key is missing, model is missing, or capability is unavailable:
- live call is blocked
- dry-run fallback is used
- `safety_blocked=True`
- `submitted=0` remains fixed

## 7. Current Limits

This layer does not:
- persist diagnostics
- run providers in a loop
- compare multiple providers automatically
- alter DecisionRouter output
- submit orders

## 8. Roadmap

- Provider key health dashboard
- One-shot result archive
- Live provider one-shot CLI
- Scenario-aware one-shot prompts
- Reliability-aware diagnostic reports
