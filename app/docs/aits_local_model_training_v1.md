# AITS LOCAL Model Training v1

## Purpose

This layer trains a minimal offline LOCAL baseline from `local_training_features.jsonl`. It produces training metrics, registry metadata, and shadow-only artifacts. It does not bind predictions to live decisions, change AI actions, or modify order safety and execution paths.

## Training Source

Inputs:

- `data/ai_decision_training/local_training_features.jsonl`
- `data/ai_decision_training/local_training_feature_summary.json`

Only records with schema `aits_local_training_feature_record.v1`, `safe_for_model_training=true`, a train/validation/holdout split, non-F feature quality, a valid action label, and at least one valid numeric target are accepted. Corrupt, duplicate, unsafe, unsplit, or leaking records are excluded.

No samples or substitute records are generated. Zero source rows are a valid `no_data` completion state.

## Feature Matrix

Nested feature groups are flattened into a stable sorted column order. Numeric values become floats, booleans become 0/1, and categorical values use a stable sorted mapping with 0 reserved for unknown or missing values. Missing numeric and boolean values use 0 only in the training matrix; the source record remains unchanged.

The feature column list, type map, categorical encoding map, and missing-value policy are model artifacts when training succeeds.

## Targets

Independent regressors are prepared for available targets:

- `action_quality_score`
- `outcome_score`
- `provider_value_score`
- `risk_adjusted_score`

Missing targets are skipped independently. Targets are retrospective outcome measurements, not live recommendations.

## Baseline Trainer

The baseline is a deterministic mean regressor implemented with the Python standard library. It learns the observed mean for each available target. This intentionally small baseline establishes a real, reproducible training and evaluation contract without adding a dependency or claiming production model quality.

Training requires at least 10 usable train rows. Below that threshold the run is recorded as `insufficient_data`; with no usable rows it is recorded as `no_data`. Neither state creates a model pickle.

## Metrics

When validation rows exist, each trained target records MAE, RMSE, R2 when defined, target mean, and prediction mean. Without evaluation data, `metrics_status` is `no_data` or `insufficient_data`; numeric metrics are not invented.

## Artifacts And Registry

Root: `data/local_models/`

Registry files:

- `registry.json`
- `latest_model.json`
- `latest_training_metrics.json`

Successful model directory:

- `model.pkl`
- `feature_columns.json`
- `encoding_map.json`
- `training_config.json`
- `metrics.json`
- `dataset_summary.json`
- `model_card.md`

Model pickle files are loaded only from the local registry path and are never accepted from provider responses or remote input. Runtime data and model artifacts are not commit targets.

Every registry record enforces:

- `safe_for_live_decision=false`
- `live_decision_enabled=false`

No-data runs record `trained=false`, a blocker, source summary hash, and counts without creating a model artifact.

## Shadow Interface

Prepared functions:

- `load_latest_local_model()`
- `predict_local_action_quality(feature_record)`
- `predict_provider_value(feature_record)`
- `predict_risk_score(feature_record)`

The functions return unavailable when no trained shadow model exists. Available predictions are numeric score metadata only. They never return a buy or sell action and are not imported by the live decision path.

## UI And Logging

`[AITS][LocalModelTraining]` logs training status, source counts, skip reason, trained targets, and the live-safety flags. Korean LIVE LOG and status text distinguish trained, insufficient-data, and no-data states and state that trained models are not connected to real trading decisions.

## Harness

`local-model-training-v1-summary --observe-only` verifies loader, feature and label builders, baseline trainer, metrics, artifacts, registry, no-data handling, shadow interface, live-binding absence, leak checks, and compatibility with the preceding LOCAL data Sprints.
