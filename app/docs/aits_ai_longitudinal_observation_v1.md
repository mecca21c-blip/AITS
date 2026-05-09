# AITS AI Longitudinal Observation Layer v1

## 1. Purpose

The AI Longitudinal Observation Layer is an AI Observatory for long-term research diagnostics.

It observes:
- provider response changes
- reliability movement
- confidence drift
- scenario distribution drift
- behavior anomalies
- safety contract violations

This layer is not connected to real trading.

## 2. Safety Contract

Always fixed:
- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

Never allowed:
- OrderAdapter calls
- ExecutionBridge calls
- Upbit order API calls
- DecisionRouter action changes
- automatic live provider loops
- background trading loops
- multi-provider auto-run
- provider auto failover
- real trading state changes

## 3. Observation Record

`AIObservationRecord` standardizes provider, state, response quality, guard, and safety fields for long-term observation.

It stores:
- provider/model/symbol/timestamp
- suggestion/next_action/confidence
- scenario/state
- quality/schema/recovery indicators
- guard degradation and cooldown state
- applied/submitted safety fields

## 4. Observation Store

`AIObservationStore` is memory-only.

It supports:
- append
- list_records
- latest
- clear
- build_summary

Summary includes total records, provider counts, symbol counts, average confidence, and average quality.

## 5. Confidence Drift

`AIConfidenceDriftDetector` compares recent confidence against baseline confidence.

Rules:
- not enough records: no drift
- absolute delta >= 0.2: drift
- volatility >= 0.25: unstable
- direction: up/down/stable/unstable

## 6. Scenario Drift

`AIScenarioDriftDetector` detects scenario concentration.

Rules:
- not enough records: no drift
- missing scenario becomes `-`
- dominant scenario ratio >= 0.7: drift

## 7. Behavior Anomaly

`AIProviderBehaviorAnomalyDetector` detects:
- average quality below 0.4: low_quality
- schema invalid ratio >= 0.3: schema_instability
- recovery used ratio >= 0.4: format_instability
- cooldown blocked: runtime_blocked
- submitted > 0: safety_violation

Severity levels:
- info
- warning
- critical

## 8. Observation Report

`AIObservationReportBuilder` combines store summary, confidence drift, scenario drift, and anomaly result.

Health labels:
- 정상
- 관찰 필요
- 불안정
- 차단 필요

## 9. Current Limits

This layer does not:
- persist files
- write DB rows
- call providers
- run background loops
- submit orders
- modify trading decisions

## 10. Roadmap

- Observation persistence skeleton
- Provider drift dashboard
- Confidence calibration history
- Scenario transition maps
- Long-term reliability research report
