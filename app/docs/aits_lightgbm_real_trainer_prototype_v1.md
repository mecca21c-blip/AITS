# AITS LightGBM Real Trainer Prototype v1

Status: Real Trainer Prototype
Scope: Small in-memory LightGBM train/predict/save/load validation

---

## 1. Purpose

This document defines AI-ARCH-16, the first real LightGBM trainer prototype for the AITS Local AI ML Engine.

The prototype consumes AI-ARCH-10 dataset rows and verifies that AITS can:

- build a feature matrix
- encode labels
- train a small LightGBM classifier
- generate predictions
- save a LightGBM text model
- reload the saved model
- persist model metadata through the preview registry store

This is not an operational trainer.

---

## 2. Real Trainer Prototype Definition

The real trainer prototype is implemented in:

```text
app/learning/lightgbm_real_trainer.py
```

Result schema:

```text
aits_lightgbm_real_trainer_result.v1
```

The prototype imports `lightgbm` and runs a small explicit training job only when called by a test or future controlled workflow.

It does not read Journal DB records automatically.

It does not start a scheduler.

It does not connect to live trading.

---

## 3. Actual Training Scope

Allowed in this prototype:

- small in-memory row list training
- LightGBM classifier training
- `predict` / probability preview
- LightGBM text model save
- LightGBM text model load
- artifact manifest creation
- evaluation report creation
- model registry entry creation
- preview registry persistence

The smoke dataset is intentionally small and synthetic.

---

## 4. Prohibited Scope

This prototype does not:

- modify `requirements.txt`
- install dependencies
- run large training jobs
- collect live operational data
- schedule automatic training
- connect to UI
- connect to Runtime loop
- connect to DecisionRouter
- connect to ExecutionBridge
- connect to OrderAdapter or OrderService
- bypass Risk Guard
- approve a model for live trading

---

## 5. Dataset Row Input

Input rows must follow:

```text
aits_lightgbm_dataset_row.v1
```

Required sections:

- `features`
- `targets`
- `quality`

Training rows must satisfy:

- `schema == aits_lightgbm_dataset_row.v1`
- `quality.usable_for_training == true`
- `targets.classifier_target` exists
- at least one primitive feature exists

The trainer does not load rows from SQLite by itself.

---

## 6. Feature Flattening / Category Encoding

Feature groups are flattened into stable column names:

```text
market__market_regime
technical__rsi
candidate__basic_score
portfolio__holding_state
ai_output__ai_action
router__final_action
```

Only primitive values are used:

- string
- int
- float
- bool
- null

Nested dict/list/raw objects are excluded.

String categories are encoded with per-column maps:

- `unknown = 0`
- observed category values start at `1`

Unknown inference categories map back to `0`.

---

## 7. Label Encoding

The default target is:

```text
classifier_target
```

Labels are encoded into integer class IDs.

At least two classes are required for classifier training.

The class map is stored in result metadata and the artifact manifest.

---

## 8. Train / Predict / Save / Load Flow

Main function:

```text
train_lightgbm_classifier_prototype()
```

Flow:

1. filter training rows
2. flatten feature groups
3. fit category maps
4. transform features into numeric matrix
5. encode labels
6. create `lightgbm.Dataset`
7. run `lightgbm.train`
8. predict on the smoke matrix
9. save model as a LightGBM text model
10. calculate SHA-256 checksum
11. build result metadata

Load/predict helpers:

```text
load_lightgbm_model()
predict_with_loaded_model()
transform_features_for_inference()
```

---

## 9. Artifact Manifest

Artifact manifest schema:

```text
aits_model_artifact_manifest.v1
```

The prototype manifest records:

- `artifact_type=prototype_text_model`
- `artifact_path`
- `checksum`
- `model_file_created=true`
- `text_model_created=true`
- `binary_created=false`
- `feature_columns`
- `category_maps`
- `label_map`

The saved file is a prototype LightGBM text model, not a live-approved model binary.

---

## 10. Evaluation Report

Evaluation report schema:

```text
aits_model_evaluation_report.v1
```

Prototype metrics:

- `training_accuracy`
- `sample_count`
- `training_row_count`
- `feature_count`
- `class_count`
- `prediction_generated`
- `prediction_count`
- `model_file_created`
- `model_file_size_bytes`
- `checksum_available`

AI-ARCH-17 fills additional distributions:

- `class_distribution`
- `prediction_distribution`
- `provider_distribution`
- `engine_role_distribution`

AI-ARCH-17 also records prototype quality:

- `prototype_quality_status=ok/warning/failed`
- `quality_notes`
- `review_required`

`warning` is not a failed training result. It means the prototype smoke dataset is too small, too perfect in-sample, or otherwise needs review before any broader training claim.

Validation-set metrics remain null until a controlled evaluation dataset exists:

- `accuracy`
- `precision`
- `recall`
- `f1`

The current `training_accuracy` is an in-sample smoke metric only. It is useful for verifying the train/predict path, but it is not model quality proof.

Artifact fields are mirrored into the report:

- `artifact_path`
- `checksum`
- `model_file_size_bytes`

Approval remains:

```text
shadow_only
```

Decision summary:

```text
prototype_train_only_not_live
```

---

## 11. Model Registry Entry

Registry entry follows AI-ARCH-04 fields:

- `provider=local_ai`
- `runtime=lightgbm`
- `model_type=lightgbm_classifier`
- `version=0.1.0-prototype`
- `status=draft`

Required notes:

- `prototype_train_only`
- `not_approved_for_live`
- `router_not_connected`

---

## 12. Registry Persistence Preview

Helper:

```text
train_and_persist_lightgbm_classifier_prototype()
```

This trains the prototype and calls:

```text
save_model_artifacts_preview()
```

Persisted metadata:

- model registry entry
- artifact manifest
- evaluation report
- trainer result

The helper does not call `set_active_model_preview()`.

The active model pointer is not changed automatically.

---

## 13. Safety / Privacy

The prototype must not store:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- raw Journal dumps
- raw OHLCV bulk arrays

Feature keys containing secret/token/key markers are excluded.

Future/outcome leakage keys are excluded from features.

Model output is not a trading signal.

`model_auto_approved=false` is mandatory.

---

## 13-A. AI-ARCH-17 Evaluation Report Fill

AI-ARCH-17 expands `build_filled_evaluation_report()` for prototype result quality tracking.

The filled report is passed into registry persistence, and `model_registry_entry.evaluation_report_id` must match the report id.

Quality status rules:

- `failed`: missing prediction, missing model file, fewer than two classes, or zero samples
- `warning`: small smoke dataset, perfect in-sample accuracy on a tiny dataset, or zero features
- `ok`: predictions exist, model file exists, class count is valid, and features exist

The smoke dataset is intentionally small, so `warning` is expected and acceptable.

The report remains a preview/shadow quality record, not a trading signal.

---

## 14. Current Disconnected State

The real trainer prototype is not wired into:

- UI
- Runtime loop
- DecisionRouter
- AIDecisionService
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard
- OpenAI/Gemini API calls
- Local AI runtime inference
- automatic training scheduler

---

## 15. Future Connections

Planned follow-up Sprints:

- AI-ARCH-17 Trainer Evaluation Report Fill
- AI-ARCH-18 Model Registry Real Artifact Integration
- AI-ARCH-19 Packaged Build Dependency Verification

---

## 16. Prohibited Layers

This Sprint explicitly prohibits:

- Router automatic connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- live trading connection
- requirements modification
- packaged build changes
