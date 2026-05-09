# AITS Live Provider Response Quality Layer v1

## 1. Purpose

The Live Provider Response Quality Layer protects AITS from malformed or unsafe AI responses before they reach UI, state, or research diagnostics.

It validates:
- broken JSON recovery
- schema completeness
- hallucinated or unsupported action values
- missing evidence/scenario/ETA structures
- confidence outliers
- safety flag drift

This is not a trading integration.

## 2. Safety Contract

Always preserved:
- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`

Never allowed:
- OrderAdapter calls
- ExecutionBridge calls
- Upbit order API calls
- DecisionRouter action changes
- automatic live provider calls
- background loops
- multi-provider auto-run

## 3. Recovery

`AIResponseRecovery` only recovers JSON text boundaries.

Recovery order:
1. accept raw text if it is already a JSON object
2. extract fenced ```json blocks
3. extract from the first `{` to the last `}`
4. fail safely without creating fields

It never invents meaning or order-related fields.

## 4. Schema Validation

`AIResponseSchemaValidator` checks required AITS shadow fields:
- suggestion
- confidence
- briefing
- evidence
- next_action
- pool_action
- scenario
- eta
- suggestion_only
- applied_to_action
- applied

It normalizes safe display/research structures and forces:
- `suggestion_only=True`
- `applied_to_action=False`
- `applied=False`

## 5. Quality Score

`AIResponseQualityScorer` produces diagnostic scores only:
- schema_score
- completeness_score
- safety_score
- consistency_score

The score must not modify action, confidence, order flow, or router behavior.

## 6. Harness Integration

`LiveProviderOneShotHarness` attaches quality diagnostics to one-shot output:
- schema_valid
- response_quality_score
- response_quality_ready
- recovery_used
- quality_warnings

These fields are attach-only diagnostics.

## 7. Current Limits

This layer does not:
- call live providers automatically
- persist response quality history
- compare providers automatically
- route orders
- modify final decisions

## 8. Roadmap

- Response quality history
- Prompt drift detector
- Provider response anomaly dashboard
- Confidence calibration research
- Scenario-specific schema checks
