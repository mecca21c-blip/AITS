# AITS LightGBM Requirements Pin Decision v1

Status: Dependency Decision
Scope: LightGBM requirements pin strategy before controlled requirements commit

---

## 1. Purpose

This document defines the decision criteria before adding LightGBM to `requirements.txt`.

It separates a successful development venv install from a reproducible project dependency declaration.

It is the decision reference for AI-ARCH-15-C Requirements Pin Commit for LightGBM.

This document does not modify `requirements.txt`.

---

## 2. Current Install State

Current controlled install state:

- `lightgbm 4.6.0` is installed in the current development venv.
- `scipy 1.17.1` was installed as a LightGBM dependency.
- `requirements.txt` has not been modified.
- AI-ARCH-14 dependency gate reports `importable=True`.
- AI-ARCH-15 controlled install/verify passed.
- AI-ARCH-16 Real Trainer Prototype passed.
- AI-ARCH-17 Trainer Evaluation Report Fill passed.
- AI-ARCH-18 Registry Real Artifact Integration passed.
- PyInstaller/package verification has not been performed.

Current venv:

```text
C:\AITS\.venv\Scripts\python.exe
```

---

## 3. Dependency Declaration Principles

Successful local install does not automatically approve a `requirements.txt` change.

Dependency declaration must be done as a separate controlled commit for reproducibility.

Before PyInstaller/package verification, distribution inclusion remains WAIT.

Adding LightGBM to requirements does not approve any model for live or trading use.

LightGBM scores and models are not order signals.

LightGBM cannot bypass Router, Risk Guard, or Execution.

---

## 4. Pin Options

Option A:

```text
lightgbm==4.6.0
```

Pros:

- Reproduces the controlled install version.
- Keeps dependency policy focused.
- Lets LightGBM manage its own transitive dependencies.

Cons:

- scipy version may vary if resolver conditions change.
- Packaging failures may require a later scipy pin.

Option B:

```text
lightgbm==4.6.0
scipy==1.17.1
```

Pros:

- Reproduces the observed venv package set more exactly.
- May help if packaging depends on exact scipy behavior.

Cons:

- Increases dependency conflict risk.
- Pins a transitive dependency before packaging evidence exists.

Option C:

```text
lightgbm>=4.6.0,<4.7.0
```

Pros:

- Allows compatible patch-level resolver freedom.

Cons:

- Less reproducible during early stabilization.
- May introduce behavior changes before packaging validation.

Decision assessment:

- Option A is preferred for the next controlled commit.
- Option B should wait for packaging evidence or repeated scipy-specific failures.
- Option C is not recommended during initial stabilization.

---

## 5. scipy Handling Criteria

`scipy 1.17.1` was installed during `pip install lightgbm`.

Directly pinning scipy increases reproducibility but also increases compatibility and resolver conflict risk.

Initial policy:

- Pin `lightgbm==4.6.0`.
- Do not directly pin `scipy==1.17.1` yet.
- Treat scipy as LightGBM's transitive dependency for AI-ARCH-15-C.
- Revisit scipy pinning if AI-ARCH-19 PyInstaller/package verification reveals scipy-specific issues.

scipy pinning should be a separate Goal if needed.

---

## 6. AI-ARCH-15-C Recommended Execution Strategy

Recommended AI-ARCH-15-C steps:

1. Check `git status`.
2. Confirm current `requirements.txt` state.
3. Add `lightgbm==4.6.0` to `requirements.txt`.
4. Run `pip install -r requirements.txt` in the AITS venv.
5. Confirm `import lightgbm` and version `4.6.0`.
6. Re-run dependency gate.
7. Re-run real trainer prototype smoke.
8. Re-run dataset builder smoke.
9. Re-run model registry real artifact smoke.
10. Inspect `git diff`.
11. Commit only the controlled requirements change and any decision-result document if requested.

AI-ARCH-15-C must not run PyInstaller build.

Packaging verification belongs to AI-ARCH-19.

---

## 7. Post-Pin Validation Checklist

Required checks after a future requirements pin:

```powershell
python -m pip show lightgbm
python -c "import lightgbm; print(lightgbm.__version__)"
python -m py_compile app/learning/lightgbm_dependency_gate.py
python -m py_compile app/learning/lightgbm_real_trainer.py
```

Expected validation:

- dependency gate report has `importable=True`
- real trainer prototype smoke passes
- registry artifact integration smoke passes
- `requirements.txt` diff is limited to the LightGBM pin
- Router/UI/Execution files remain unchanged

---

## 8. Rollback Policy

If the requirements pin causes problems:

- Revert the requirements pin commit.
- If the venv is polluted, recreate the venv or uninstall LightGBM/scipy in a controlled maintenance step.
- If PyInstaller fails, exclude the pin commit from release branches until AI-ARCH-19 resolves packaging.
- LightGBM unavailable fallback remains `dry_run_trainer_skeleton`.
- Local AI registry artifacts are preview artifacts and have no live trading impact.

---

## 9. Decision Gate

GO:

- `lightgbm==4.6.0` pin candidate is accepted.
- scipy direct pin is explicitly deferred.
- AI-ARCH-15-C can proceed as a controlled requirements commit.
- Router/UI/Execution remain disconnected.

WAIT:

- Distribution inclusion before PyInstaller verification.
- scipy direct pin decision.
- Additional Python 3.14 compatibility review, if packaging reveals issues.

FAIL:

- Proposal adds large unrelated dependencies.
- LightGBM/scipy version policy is unclear.
- Dependency pin is treated as live/trading approval.
- Router/UI/Execution changes are included.

---

## 10. Recommended Decision

Recommended:

- AI-ARCH-15-C should pin only `lightgbm==4.6.0` in `requirements.txt`.
- Do not directly pin `scipy==1.17.1` yet.
- Keep scipy as a transitive dependency unless packaging evidence requires otherwise.
- Run AI-ARCH-19 for PyInstaller/package verification before distribution inclusion.
- Keep deployment/distribution status as WAIT until AI-ARCH-19.

---

## 11. Future Goal Map

Recommended sequence:

- AI-ARCH-15-C Requirements Pin Commit for LightGBM
- AI-ARCH-19 Packaged Build Dependency Verification
- AI-ARCH-20 Local AI Shadow Training Loop Preview
- AI-ARCH-21 Local AI Model Promotion Gate

Optional:

- AI-ARCH-18-B Real Artifact Registry Report Export

---

## 12. Safety / Privacy

This dependency decision does not change safety posture.

Mandatory rules:

- Do not store API keys.
- Do not store account secrets.
- Do not store raw Journal dumps.
- Do not store bulk raw OHLCV arrays.
- Do not automatically apply training results to live trading.
- Keep `model_auto_approved=false`.
- Do not automatically set `active_model`.
- Do not bypass Router, Risk Guard, or Execution.
- Do not connect to live trading.
- Maintain the `submitted=0` principle.

---

## 13. Current Disconnected State

Current disconnected state remains:

- UI connection: none
- Router connection: none
- Execution connection: none
- Order connection: none
- Risk Guard connection: none
- Runtime loop connection: none
- automatic training scheduler: none

---

## 14. Current Decision

Decision for this document:

```text
GO for AI-ARCH-15-C controlled requirements pin of lightgbm==4.6.0.
WAIT for scipy direct pin.
WAIT for packaged distribution inclusion until AI-ARCH-19.
```
