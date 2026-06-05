# AITS LightGBM Dependency Gate v1

Status: Dependency Gate Preview
Scope: LightGBM availability, packaging risk, fallback policy, and trainer readiness report

---

## 1. Purpose

The LightGBM Dependency Gate checks whether LightGBM can be used in the current environment before AITS introduces a real trainer prototype.

It produces a dependency status report.

It does not install LightGBM.

It does not modify requirements.

It does not train a model.

---

## 2. Dependency Gate Definition

The gate answers:

- Is `lightgbm` discoverable?
- Can it be imported?
- What version is available?
- What packaging risks should be reviewed?
- Can the future Real Trainer Prototype proceed?
- What fallback remains available?

The gate is a report builder only.

---

## 3. Not Real Training

This Sprint explicitly does not:

- import LightGBM for training
- call LightGBM training APIs
- create a model binary
- run Local AI inference
- connect to Router
- connect to Execution

---

## 4. No Dependency Modification

The gate does not:

- run `pip install`
- modify `requirements.txt`
- modify lock files
- download packages
- install native binaries

Any dependency addition must be handled by a separate controlled Goal.

---

## 5. Dependency Gate Report Schema

Schema:

```text
aits_lightgbm_dependency_gate.v1
```

Top-level sections:

- `dependency`
- `environment`
- `packaging_risk`
- `fallback_policy`
- `readiness`
- `safety`
- `meta`

---

## 6. Dependency Check

The dependency check uses:

- `importlib.util.find_spec("lightgbm")`
- `importlib.import_module("lightgbm")` only when discoverable

Recorded fields:

- `package_name`
- `required_for_real_trainer`
- `installed`
- `importable`
- `version`
- `import_error`

Import failures are captured in the report and do not crash the app.

---

## 7. Environment Info

Recorded fields:

- Python version
- platform string
- machine
- executable
- Windows flag
- packaged runtime flag

The packaged runtime flag is based on:

```text
getattr(sys, "frozen", False)
```

---

## 8. Packaging Risk

Risk dimensions:

- `pyinstaller_risk_level`
- `windows_wheel_risk`
- notes

Baseline notes:

- LightGBM may require wheel/native binary compatibility checks.
- PyInstaller packaging must be validated separately.
- Real Trainer must not be enabled until the dependency gate is reviewed.

Windows environments are evaluated conservatively.

Packaged environments are high-risk until separately validated.

---

## 9. Fallback Policy

Fallback remains available regardless of LightGBM installation state.

Default:

```json
{
  "fallback_available": true,
  "fallback_mode": "dry_run_trainer_skeleton",
  "real_training_enabled": false,
  "trainer_skeleton_available": true,
  "dependency_required_before_real_training": true
}
```

---

## 10. Readiness

Readiness fields:

- `real_trainer_prototype_allowed`
- `dependency_action_required`
- `recommended_next_action`

Rules:

- If LightGBM is importable, a future Real Trainer Prototype may be attempted after packaging risk review.
- If LightGBM is not importable, controlled dependency installation or addition is required.
- Dry-run trainer skeleton remains the fallback.

`real_trainer_prototype_allowed=True` is not live-trading approval.

---

## 11. Safety / Privacy

Safety defaults:

- `requirements_modified=false`
- `pip_install_executed=false`
- `training_executed=false`
- `model_binary_created=false`
- `router_connected=false`
- `execution_connected=false`
- `ui_connected=false`

The report must not include:

- API keys
- OpenAI key
- Gemini key
- Upbit keys
- account secrets
- raw Journal dumps
- raw OHLCV bulk data

---

## 12. Current Disconnected State

This gate is not wired into:

- UI
- Runtime loop
- DecisionRouter
- AIDecisionService
- ExecutionBridge
- OrderAdapter
- OrderService
- Risk Guard
- OpenAI/Gemini API calls
- Local AI inference
- Local AI training
- automatic scheduler

---

## 13. Future Connections

Possible follow-up Sprints:

- AI-ARCH-15 LightGBM Real Trainer Prototype
- AI-ARCH-14-B Controlled Dependency Install Goal
- PyInstaller packaging validation
- dependency report UI preview

---

## 14. Prohibited Connections

This Sprint explicitly prohibits:

- Router auto connection
- UI connection
- Execution connection
- Order connection
- Risk Guard bypass
- pip install
- requirements changes
- model training
- model binary generation
