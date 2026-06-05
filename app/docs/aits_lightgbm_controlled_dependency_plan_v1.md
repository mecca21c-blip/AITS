# AITS Controlled LightGBM Dependency Plan v1

Status: Controlled Dependency Plan
Scope: LightGBM install, verification, packaging, rollback, and fallback strategy before real trainer work

---

## 1. Document Purpose

This document defines the controlled plan for introducing LightGBM into the AITS Local AI ML Engine.

It exists before any dependency installation or requirements change.

The plan is the baseline for:

```text
AI-ARCH-15 Controlled LightGBM Install / Verify
```

Goals:

- protect AITS runtime stability
- prevent accidental dependency drift
- define packaging and Windows validation requirements
- define rollback criteria
- keep dry-run fallback available

---

## 2. Current Dependency Gate Result

AI-ARCH-14 result:

- `lightgbm importable=False`
- `real_trainer_prototype_allowed=False`
- `fallback_mode=dry_run_trainer_skeleton`
- `requirements_modified=False`
- `pip_install_executed=False`
- `training_executed=False`
- `model_binary_created=False`
- Router/UI/Execution connection: none

Current state:

```text
LightGBM is not available in the current environment.
```

This is not an application failure.

It is a controlled fallback state.

---

## 3. LightGBM Introduction Principles

LightGBM is one component of the Local AI ML Engine.

LightGBM does not replace the Reason Runtime.

LightGBM score is not an order signal.

LightGBM models must not bypass:

- Router
- Risk Guard
- Execution Layer

Installation success is not live approval.

Training success is not live approval.

Any model must pass preview/shadow validation before a later stage can consider recommendation or runtime integration.

---

## 4. Controlled Install Strategy

### A. Pre-check

Before installing anything in AI-ARCH-15:

- record `git status --short`
- record current commit hash
- record current `requirements.txt` state
- record Python version
- record venv path
- check whether a PyInstaller spec exists
- confirm no unrelated files are staged

### B. Candidate Install Methods

Candidate methods:

- `pip install lightgbm`
- add a pinned LightGBM version to requirements, then install

Required checks:

- Windows wheel compatibility
- Python version compatibility
- import test in current venv
- whether native binaries or DLLs are required

### C. Recommended Order

1. Run installation only in a separate controlled Goal.
2. Verify `import lightgbm`.
3. Record `lightgbm.__version__`.
4. Re-run Dependency Gate.
5. Re-run Trainer Skeleton smoke test.
6. Re-run Dataset Builder smoke test.
7. Check packaging impact separately.
8. Decide whether requirements should be updated only after install verification.

### D. Version Pin Policy

Recommended:

- record the exact version that imports successfully
- avoid broad version ranges at first
- do not include LightGBM in distribution release before PyInstaller validation
- apply requirements changes only in a controlled commit

---

## 5. Packaging / PyInstaller Risk

LightGBM may involve native binary and wheel compatibility issues.

Windows risk items:

- wheel availability for the active Python version
- native DLL load behavior
- CPU/GPU runtime assumptions
- antivirus or enterprise environment restrictions

PyInstaller risk items:

- hidden import requirements
- DLL or native library inclusion
- onedir packaging validation
- executable import test after packaging
- build size increase
- environment-specific failures that do not appear in dev mode

Policy:

- do not include LightGBM in normal user distribution before packaging validation
- test packaged exe separately
- keep dry-run trainer fallback available

---

## 6. Fallback Policy

If LightGBM is unavailable:

- keep `dry_run_trainer_skeleton`
- keep Dataset Builder working
- keep Evaluation Dashboard working
- keep Model Registry Persistence Preview working
- disable only real trainer execution

Dependency unavailable state is a controlled fallback, not a runtime error.

Fallback must not affect:

- Router
- UI
- Execution
- Order
- Risk Guard

---

## 7. Rollback Policy

If installation fails before requirements changes:

- no code rollback is required
- keep dry-run trainer skeleton
- document failure in the dependency gate report

If requirements are changed and validation fails:

- revert the requirements commit
- re-run dependency gate
- confirm fallback mode is restored

If venv becomes polluted:

- rebuild the venv, or
- uninstall LightGBM from the venv

If packaged build fails:

- isolate or revert the LightGBM inclusion commit
- keep packaged release on fallback path

Local registry preview artifacts do not contain model binaries and do not require deletion.

`active_model` preview pointer has no live effect.

---

## 8. Validation Checklist for AI-ARCH-15

Required checks:

```powershell
python -m pip show lightgbm
python -c "import lightgbm; print(lightgbm.__version__)"
python -m py_compile app/learning/lightgbm_dependency_gate.py
```

Then:

- regenerate dependency gate report
- confirm `importable=True`
- confirm `training_executed=False`
- clearly record whether requirements were modified
- re-run trainer skeleton smoke test
- re-run dataset builder smoke test
- re-run model registry persistence smoke test
- confirm Router/UI/Execution remain unconnected

---

## 9. Decision Gate

### GO

Proceed to a real trainer prototype only if:

- `lightgbm importable=True`
- version is recorded
- dependency gate smoke test passes
- trainer skeleton smoke test passes
- requirements change status is explicit
- Router/UI/Execution remain unconnected

### WAIT

Hold if:

- import works but PyInstaller risk is not reviewed
- install works but version compatibility is unclear
- requirements update policy is undecided

### FAIL

Stop and rollback or keep fallback if:

- import fails
- Python execution errors occur
- existing learning module smoke tests fail
- requirements are unintentionally changed
- unrelated files are modified broadly
- Router/UI/Execution changes appear

---

## 10. Future Goal Map

Recommended order:

1. AI-ARCH-15 Controlled LightGBM Install / Verify
2. AI-ARCH-16 LightGBM Real Trainer Prototype
3. AI-ARCH-17 Trainer Evaluation Report Fill
4. AI-ARCH-18 Model Registry Real Artifact Integration
5. AI-ARCH-19 Packaged Build Dependency Verification
6. AI-ARCH-20 Local AI Shadow Training Loop Preview

---

## 11. Safety / Privacy

The LightGBM dependency plan must preserve:

- API key storage prohibition
- account secret storage prohibition
- raw Journal dump storage prohibition
- raw OHLCV bulk storage prohibition
- no automatic live application of training results
- `model_auto_approved=false`
- no Router/Risk Guard/Execution bypass
- no live trading connection
- `submitted=0` principle until explicit approval

---

## 12. Current Disconnected State

Current state:

- UI connection: none
- Router connection: none
- Execution connection: none
- Order connection: none
- Risk Guard connection: none
- Runtime loop connection: none
- real trainer: none
- real model binary: none

This document does not change runtime behavior.

---

## 13. AI-ARCH-15 Execution Boundary

AI-ARCH-15 may perform a controlled dependency installation only if the Goal explicitly allows it.

Until then:

- do not run `pip install`
- do not edit requirements
- do not train LightGBM
- do not connect any trainer to AITS runtime

