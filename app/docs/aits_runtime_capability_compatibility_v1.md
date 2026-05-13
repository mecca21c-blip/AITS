# AITS Runtime Capability & Compatibility v1

## Scope

This layer evaluates provider/model/runtime capabilities and compatibility only.
It does not auto-run features, call providers, create UI widgets, or execute trades.

## Capability Registry

`app/services/ai_runtime_capability_registry.py` defines
`AIRuntimeCapabilityProfile` and registry lookup.

Supported behavior:

- `openai`: dry-run/live-one-shot/structured-json/state-context/observation/replay/snapshot-export enabled
- `gemini`: dry-run/live-one-shot/structured-json/state-context/observation/replay/snapshot-export enabled
- `ollama`: local runtime enabled, live one-shot disabled by default
- `unknown`: mostly disabled, dry-run only

## Feature Matrix

`app/services/ai_runtime_feature_matrix.py` converts a profile into normalized
feature flags and counts:

- `features`
- `enabled_count`
- `disabled_count`

## Compatibility Checker

`app/services/ai_runtime_compatibility_checker.py` checks feature requirements:

- `one_shot_dry_run` -> `supports_dry_run`
- `one_shot_live` -> `supports_live_one_shot` + `supports_structured_json`
- `state_aware_prompt` -> `supports_state_context`
- `observation_report` -> `supports_observation`
- `runtime_replay` -> `supports_replay`
- `snapshot_export` -> `supports_snapshot_export`
- `local_runtime` -> `supports_local_runtime`

Unknown features return `compatible=False`, `reason="unknown_feature"`.

## Capability Report

`app/services/ai_runtime_capability_report.py` compacts profile/matrix/
compatibility into:

- `provider`
- `model`
- `compatible`
- `enabled_count`
- `disabled_count`
- `summary_line`
- `warnings`

## Formatter

`app/services/ai_runtime_capability_formatter.py` maps report + matrix to
UI-ready output:

- `title`
- `summary`
- `badges`
- `features`
- `metadata`

## Harness Attach-Only Structure

`LiveProviderOneShotHarness.run_one_shot(...)` attaches:

- `runtime_capability_ready`
- `runtime_capability_profile`
- `runtime_feature_matrix`
- `runtime_compatibility`
- `runtime_capability_report`
- `runtime_capability_formatted`

Requested feature selection:

- `allow_live=False` -> `one_shot_dry_run`
- `allow_live=True` -> `one_shot_live`

Compatibility output never changes provider execution path automatically in this layer.

## Safety Contract

The layer keeps:

- `shadow_only=True`
- `suggestion_only=True`
- `applied=False`
- `applied_to_action=False`
- `real_order=False`
- `submitted=0`
- `research_mode=True`

No provider calls, no UI creation, no order execution, no failover automation.
