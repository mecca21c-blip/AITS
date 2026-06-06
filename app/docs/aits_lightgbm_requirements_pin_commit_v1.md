# AITS LightGBM Requirements Pin Commit v1

Status: Requirements Pin Result
Scope: Controlled LightGBM dependency pin and smoke verification

---

## 1. Goal

AI-ARCH-15-C pins LightGBM in `requirements.txt` according to AI-ARCH-15-B.

This Goal adds only:

```text
lightgbm==4.6.0
```

It does not directly pin scipy.

---

## 2. Change Summary

Changed file:

```text
requirements.txt
```

Added dependency:

```text
lightgbm==4.6.0
```

No other dependency versions were changed.

`scipy==1.17.1` was not added directly.

---

## 3. Install / Verification Commands

Requirements install verification:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

LightGBM import/version:

```powershell
.\.venv\Scripts\python.exe -c "import lightgbm; print(lightgbm.__version__)"
```

Dependency gate:

```powershell
.\.venv\Scripts\python.exe -m py_compile app/learning/lightgbm_dependency_gate.py
```

Real trainer:

```powershell
.\.venv\Scripts\python.exe -m py_compile app/learning/lightgbm_real_trainer.py
```

Smoke tests executed:

- dependency gate report
- real trainer prototype
- registry real artifact persistence

---

## 4. Verification Results

`pip install -r requirements.txt` result:

- `python-dotenv>=1.0.0`: already satisfied
- `mplfinance`: already satisfied
- `lightgbm==4.6.0`: already satisfied
- `scipy 1.17.1`: present as LightGBM transitive dependency

LightGBM import/version:

```text
4.6.0
```

Dependency gate:

- schema: `aits_lightgbm_dependency_gate.v1`
- package: `lightgbm`
- importable: `True`
- version: `4.6.0`
- real_trainer_prototype_allowed: `True`
- training_executed: `False`
- json_exists: `True`

Real trainer smoke:

- schema: `aits_lightgbm_real_trainer_result.v1`
- train_status: `success`
- lightgbm_version: `4.6.0`
- model_file_created: `True`
- training_accuracy: populated
- quality_status: `warning`
- approval_status: `shadow_only`
- router_connected: `False`
- execution_connected: `False`
- model_auto_approved: `False`

Registry real artifact smoke:

- train_status: `success`
- registry_updated: `True`
- active_model_updated: `False`
- consistent: `True`
- artifact_path_match: `True`
- eval_checksum_match: `True`
- entry_status: `draft`
- router_connected: `False`
- execution_connected: `False`

---

## 5. scipy Handling

scipy remains a transitive dependency of LightGBM.

Observed current venv version:

```text
scipy 1.17.1
```

No direct scipy pin was added in this Goal.

If AI-ARCH-19 packaging verification finds scipy-specific issues, scipy pinning should be handled by a separate controlled Goal.

---

## 6. PyInstaller / Package Status

PyInstaller build was not executed.

PyInstaller spec was not modified.

Packaged executable verification remains WAIT until AI-ARCH-19.

---

## 7. Safety

This Goal did not change trading behavior.

Safety status:

- actual training: smoke/prototype only
- Router connection: none
- UI connection: none
- Execution connection: none
- Order connection: none
- Risk Guard bypass: none
- live trading impact: none
- model_auto_approved: `False`
- active_model automatic update: none
- submitted=0 principle: maintained

---

## 8. Decision

Decision:

```text
GO: requirements pin completed for lightgbm==4.6.0.
WAIT: scipy direct pin.
WAIT: PyInstaller/package distribution verification.
```

---

## 9. Next Goal Candidates

- AI-ARCH-19 Packaged Build Dependency Verification
- AI-ARCH-20 Local AI Shadow Training Loop Preview
- AI-ARCH-21 Local AI Model Promotion Gate
