# AITS Observation Integration & Reporting v1

## Scope

This layer connects one-shot AI dry-run output to an observation record, memory-only
observation store, drift/anomaly detectors, and compact observation reports.

It is an AI observation and reporting layer only. It is not a trading execution path.

## Observation Adapter

`app/services/ai_observation_adapter.py` provides `AIObservationAdapter`.

`from_one_shot_result(result, symbol="KRW-BTC")` converts a
`LiveProviderOneShotHarness` result dictionary into `AIObservationRecord`.

Mapping summary:

- `provider` from `result["provider"]`
- `model` from `result.get("model", "-")`
- `symbol` from the method argument
- `suggestion` from `result.get("suggestion", "skip")`
- `next_action` from `result.get("next_action", "wait")`
- `confidence` from `shadow_record.confidence`, defaulting to `0.0`
- `scenario` from `shadow_record.scenario.label_ko`, then `name`, then `-`
- `state` from `result.get("state", "-")`
- `quality_score` from `result.get("response_quality_score", 0.0)`
- `schema_valid` from `result.get("schema_valid", False)`
- `recovery_used` from `result.get("recovery_used", False)`
- `guard_degraded` from `result.get("degraded", False)`
- `cooldown_blocked` from `result.get("cooldown_blocked", False)`
- `applied` is always `False`
- `submitted` is always `0`

Metadata always includes `shadow_only=True`, `suggestion_only=True`,
`applied=False`, `applied_to_action=False`, `real_order=False`, `submitted=0`,
`research_mode=True`, and `source="one_shot"`.

## Observation Pipeline

`app/services/ai_observation_pipeline.py` provides `AIObservationPipeline`.

`run_once(one_shot_result, symbol="KRW-BTC")` performs the dry-run flow:

1. Convert one-shot result to `AIObservationRecord`.
2. Append the record to memory-only `AIObservationStore`.
3. Run `AIConfidenceDriftDetector`.
4. Run `AIScenarioDriftDetector`.
5. Run `AIProviderBehaviorAnomalyDetector`.
6. Build `AIObservationReport`.

The pipeline does not call any provider, does not submit orders, and does not
write files.

## Report Formatter

`app/services/ai_observation_report_formatter.py` provides
`AIObservationReportFormatter`.

`format_report(report)` returns:

- `title`: `AI 관측 리포트`
- `status`: compact display status
- `summary`: report summary line
- `badges`: compact UI/log badges
- `metadata`: report metadata

Badge rules:

- `정상` -> `정상`
- `관찰 필요` -> `주의`
- `불안정` -> `불안정`
- `차단 필요` -> `차단`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` attaches observation fields to the
existing one-shot result:

- `observation_ready`
- `observation_health_label`
- `observation_summary_line`
- `observation_report`
- `observation_formatted`

Attachment is best-effort. If observation formatting fails, the original
one-shot result is still returned with `observation_ready=False`.

## Safety Contract

The observation integration must preserve:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

This layer must not call `OrderAdapter`, `ExecutionBridge`, or any Upbit order
API. It must not alter `DecisionRouter` action behavior, start a background
trading loop, invoke automatic live provider retries, run multiple providers, or
perform provider failover.

The observation layer is attach-only and research-only.
