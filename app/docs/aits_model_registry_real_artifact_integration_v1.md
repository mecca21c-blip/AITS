# AITS Model Registry Real Artifact Integration v1

Status: Real Artifact Integration Preview
Scope: LightGBM prototype text model file persistence in Local AI registry

---

## 1. Purpose

AI-ARCH-18 integrates the real LightGBM prototype model file produced by AI-ARCH-16/17 into the Local AI Model Registry persistence structure.

The Goal is to store and verify model artifact metadata more clearly:

- model text file
- checksum
- file size
- feature schema
- category maps
- label map
- evaluation report link
- registry entry link

This is not live model approval.

---

## 2. Real Artifact Integration Definition

The real artifact integration stores the LightGBM prototype text model alongside registry metadata.

The artifact remains a prototype/shadow candidate.

It is not connected to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 3. Registry model.txt Structure

Registry root:

```text
data/local_ai_registry
```

Model directory:

```text
data/local_ai_registry/
  models/
    {model_id}/
      model_registry_entry.json
      artifact_manifest.json
      evaluation_report.json
      trainer_run_summary.json
      model.txt
```

`model.txt` is a LightGBM text model prototype artifact.

It is not a live-approved model binary.

---

## 4. Artifact Manifest Fields

The artifact manifest keeps schema:

```text
aits_model_artifact_manifest.v1
```

AI-ARCH-18 enriches:

- `artifact_path`
- `checksum`
- `model_file_created`
- `text_model_created`
- `model_file_size_bytes`
- `source_model_path`
- `registry_model_path`
- `binary_created=false`

`binary_created=false` is retained to avoid confusing this prototype text model with a packaged/live-approved model artifact.

---

## 5. Evaluation Report Artifact Link

The evaluation report artifact section is updated to match the registry model file:

- `artifact.checksum`
- `artifact.artifact_path`
- `artifact.model_file_size_bytes`

The report remains:

```text
approval_status=shadow_only
```

---

## 6. Model Registry Entry Link

The model registry entry is updated with:

- `artifact_path`
- `checksum`
- `status=draft`
- `not_approved_for_live`
- `real_prototype_artifact_registered`

The registry entry must not automatically become `approved`.

---

## 7. Metadata Consistency Validation

AI-ARCH-18 adds consistency validation:

- artifact manifest checksum matches evaluation report artifact checksum
- artifact manifest path matches model registry entry artifact path
- evaluation report id matches model registry entry evaluation report id
- registry entry status is not `approved`

The validation result is returned in:

```text
metadata_consistency
```

---

## 8. active_model Rule

The real artifact persistence helper does not set `active_model`.

`active_model.json` remains a preview pointer controlled by explicit future Goals.

No automatic activation is allowed.

---

## 9. Approval Rule

This Goal does not approve models.

Status remains:

```text
draft
```

Evaluation approval remains:

```text
shadow_only
```

`model_auto_approved=false` remains mandatory.

---

## 10. Preview Artifact vs Live-Approved Model

Preview/shadow artifact:

- created by smoke/prototype training
- stored for inspection and future evaluation
- not connected to execution
- not approved for trading

Live-approved model:

- future concept only
- requires packaging verification
- requires safety review
- must still pass Router/Risk Guard/Execution boundaries

AI-ARCH-18 only creates preview/shadow artifacts.

---

## 11. Safety / Privacy

The registry artifact store must not contain:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw private account details
- raw order secrets
- raw Journal dumps
- raw OHLCV bulk arrays

Model artifacts are not order signals.

LightGBM scores do not bypass Router/Risk Guard/Execution.

---

## 12. Current Disconnected State

This integration is not wired into:

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

## 13. Future Work

Recommended next Goals:

- AI-ARCH-15-B requirements pin decision
- AI-ARCH-19 Packaged Build Dependency Verification
- AI-ARCH-20 Local AI Shadow Training Loop Preview

---

## 14. Prohibited Layers

This Sprint explicitly prohibits:

- Router automatic connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- live trading connection
- requirements modification
- packaged build changes
