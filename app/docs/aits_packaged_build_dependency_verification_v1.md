# AITS Packaged Build Dependency Verification v1

Status: Packaging Verification Result
Scope: LightGBM/scipy packaged dependency readiness check

---

## 1. Goal

AI-ARCH-19 checks whether the LightGBM dependency pinned in AI-ARCH-15-C can be verified in a PyInstaller packaged environment.

This Goal does not modify PyInstaller spec files.

This Goal does not modify requirements.

This Goal does not connect Local AI learning code to Router, UI, Runtime, Execution, Order, or Risk Guard.

---

## 2. Precheck State

Current commit before this Goal:

```text
89fd1a4
```

Python executable:

```text
C:\AITS\.venv\Scripts\python.exe
```

Python version:

```text
3.14.4 (MSC v.1944 64 bit AMD64)
```

Development venv imports:

```text
lightgbm 4.6.0
scipy 1.17.1
```

Requirements state:

```text
lightgbm==4.6.0
```

No direct scipy pin exists in `requirements.txt`.

PyInstaller check:

```text
python -m PyInstaller --version
```

Result:

```text
No module named PyInstaller
```

Project spec files:

```text
none found outside virtualenv/site-packages
```

`dist` / `build` state:

```text
not present
```

---

## 3. Verification Method

Because PyInstaller is not installed and no app `.spec` file exists in the project tree, a packaged app build could not be performed in this Goal.

To prepare a future packaged entrypoint and verify the probe logic, a standalone probe module was added:

```text
app/learning/packaged_lightgbm_probe.py
```

The probe checks:

- LightGBM import/version
- scipy import/version
- dependency gate report generation
- tiny real trainer smoke
- safety flags

The probe is not wired into runtime.

The probe is not a UI command.

The probe is not a Router/Execution path.

---

## 4. Build Result

PyInstaller build result:

```text
not executed
```

Reason:

- PyInstaller is not installed in the current venv.
- No project app spec file was found.
- Installing PyInstaller is outside this Goal.
- Creating or modifying a spec file is outside this Goal.

dist generated:

```text
no
```

exe generated:

```text
no
```

---

## 5. Probe Result

Venv probe command:

```powershell
.\.venv\Scripts\python.exe -m app.learning.packaged_lightgbm_probe
```

Result summary:

- schema: `aits_packaged_lightgbm_probe.v1`
- frozen: `False`
- executable: `C:\AITS\.venv\Scripts\python.exe`
- lightgbm ok: `True`
- lightgbm version: `4.6.0`
- scipy ok: `True`
- scipy version: `1.17.1`
- dependency_gate ok: `True`
- dependency_gate importable: `True`
- dependency_gate version: `4.6.0`
- real_trainer_smoke ok: `True`
- real_trainer train_status: `success`
- model_file_created: `True`
- prediction_executed: `True`

Safety flags:

- router_connected: `False`
- execution_connected: `False`
- ui_connected: `False`
- training_scope: `tiny_probe_only`
- model_auto_approved: `False`

---

## 6. Packaged Dependency Result

Packaged dependency probe:

```text
not executed
```

Reason:

- no PyInstaller installation
- no project spec
- no packaged executable
- no packaged probe entrypoint

Confirmed only in development venv:

- LightGBM import works
- scipy import works
- dependency gate works
- tiny real trainer smoke works

Packaged import status remains unverified.

---

## 7. Packaging Risk Assessment

Current risk status:

- hidden import need: unknown
- DLL/native dependency issue: unknown
- scipy packaging issue: unknown
- spec modification need: likely, but unconfirmed
- probe entrypoint need: yes

Observed blocker:

```text
PyInstaller is unavailable in the current venv and no app spec exists.
```

This is a packaging infrastructure gap, not a LightGBM runtime failure.

---

## 8. Decision

Decision:

```text
WAIT
```

Reason:

- Development venv probe passed.
- Packaged build could not be performed.
- Packaged import could not be verified.
- Existing app has no packaged probe entrypoint.
- Spec creation/fix must be handled by a separate Goal.

Not FAIL:

- LightGBM/scipy imports did not fail in venv.
- Dependency gate did not fail in venv.
- Real trainer tiny smoke did not fail in venv.

Not GO:

- There is no packaged executable verification yet.

---

## 9. Safety

No live trading was performed.

No Router connection was added.

No UI connection was added.

No Execution connection was added.

No Order connection was added.

No Risk Guard bypass was added.

No active model was set.

No model status was changed to approved.

No operational data training was performed.

The `submitted=0` principle remains intact.

---

## 10. Next Recommended Goal

Recommended follow-up:

```text
AI-ARCH-19-B Packaged Probe Entrypoint
```

Purpose:

- Add a controlled packaged probe entrypoint.
- Decide whether to install PyInstaller as a packaging dependency or use an existing build environment.
- Create or identify an app spec without changing runtime behavior.

Possible later Goals:

- AI-ARCH-19-C PyInstaller Spec LightGBM Fix
- AI-ARCH-19-D Packaged Trainer Smoke
- AI-ARCH-20 Local AI Shadow Training Loop Preview
