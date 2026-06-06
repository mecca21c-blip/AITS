# AITS PyInstaller Controlled Install / Build Plan v1

## 1. Document Purpose

This document defines the controlled plan for introducing PyInstaller-based packaged build verification in AITS.

It exists to resolve the AI-ARCH-19 WAIT state without rushing into installer changes, spec generation, or packaged build execution. It also defines the packaging infrastructure needed to verify LightGBM and scipy in a packaged environment.

This document is a planning artifact only. It does not install PyInstaller, modify requirements, create or edit a spec file, run a packaged build, or connect anything to Router, UI, Execution, Order, Risk Guard, or runtime loops.

## 2. Current AI-ARCH-19 Result Summary

AI-ARCH-19 verified the current development venv state and found:

- venv LightGBM import: OK
- venv scipy import: OK
- LightGBM version: 4.6.0
- scipy version: 1.17.1
- venv dependency gate: OK
- venv tiny real trainer smoke: OK
- PyInstaller: not installed
- Project `.spec` file: none
- `dist/` directory: none
- `build/` directory: none
- Packaged probe entrypoint: none
- Packaged LightGBM/scipy import verification: not performed
- Decision: WAIT

The WAIT decision means the development dependency path is healthy, but the packaged dependency path is not yet testable.

## 3. PyInstaller Adoption Principles

- PyInstaller install success is not deployment success.
- PyInstaller spec generation success is not packaged dependency verification completion.
- Packaged exe import verification must pass before LightGBM is considered distribution-ready.
- LightGBM packaged import verification is a separate dependency stability check.
- PyInstaller adoption does not approve live trading.
- PyInstaller adoption does not connect Router, UI, Execution, Order, or Risk Guard.
- Packaging verification is for Local AI dependency stability only.
- LightGBM model output remains a Local AI ML signal candidate, not an order signal.

## 4. Controlled Install Strategy

AI-ARCH-19-C should perform only a controlled PyInstaller install and verification.

### A. Precheck

Before installation, record:

- `git status --short`
- current commit hash
- Python version
- venv executable path
- requirements state
- LightGBM/scipy import state
- current PyInstaller missing state

### B. Install Options

Option A:

- Run `python -m pip install pyinstaller`
- Defer requirements pinning.
- Use this for initial controlled verification.

Option B:

- Add a PyInstaller pin to requirements first, then install.
- This is not recommended for the initial stage because packaging viability is still unknown.

Recommended:

- In AI-ARCH-19-C, install PyInstaller only into the current venv in a controlled way.
- Do not modify requirements in AI-ARCH-19-C.
- Decide PyInstaller pinning only after packaged probe and main app packaging behavior are understood.

## 5. PyInstaller Version Pin Strategy

- Record the installed PyInstaller version after controlled install.
- Do not immediately pin PyInstaller in `requirements.txt`.
- PyInstaller is a build tool dependency, not a runtime trading dependency.
- Decide later whether PyInstaller belongs in `requirements.txt`, a future `requirements-dev.txt`, or another build dependency policy.
- Pinning should happen in a separate controlled Goal after packaging behavior is stable.

## 6. Probe Entrypoint Strategy

AI-ARCH-19 created `app/learning/packaged_lightgbm_probe.py`, and it works in the venv. Packaged execution still needs an entrypoint.

Option A:

- Create a separate probe runner script, for example `tools/run_packaged_lightgbm_probe.py`.
- Or use `app/learning/packaged_lightgbm_probe.py` directly as the PyInstaller entry script.

Option B:

- Add a `--probe-lightgbm` CLI argument to `run.py`.
- This changes the main runtime entrypoint and is not recommended for the initial packaging probe.

Option C:

- Create a separate PyInstaller probe spec for LightGBM packaged verification.
- Keep it separate from the main app spec.
- This is recommended for initial verification.

Recommended:

- First build a separate probe entry script and probe spec.
- Do not touch `run.py` or `app/ui/app_gui.py` for the first packaged dependency probe.

## 7. Build Strategy

The packaging work should be split into separate Goals:

- AI-ARCH-19-C: Controlled PyInstaller Install / Verify
  - Install PyInstaller in the venv.
  - Verify version/import.
  - Re-run venv LightGBM/scipy and packaged probe module checks.
  - Do not create spec files.
  - Do not build.

- AI-ARCH-19-D: Packaged LightGBM Probe Build
  - Create a separate probe runner/spec.
  - Prefer onedir for initial inspection.
  - Run packaged probe.
  - Verify LightGBM/scipy import.
  - Verify dependency gate.
  - Run tiny trainer smoke if feasible.

- AI-ARCH-19-E: Main App PyInstaller Spec Planning
  - Plan the main app spec.
  - Identify hidden imports, data files, DLL/native dependency handling, and output policy.

- AI-ARCH-19-F: Main App Packaged Dependency Verification
  - Verify dependency behavior in the packaged main app environment.
  - Keep Router/UI/Execution behavior unchanged.

## 8. onedir / onefile Decision Criteria

Initial verification should use onedir.

Reasons:

- Native DLL files are easier to inspect.
- LightGBM/scipy file inclusion is easier to confirm.
- Runtime import failures are easier to debug.
- Build output is easier to compare across attempts.

onefile can be considered later for distribution packaging after onedir dependency behavior is stable.

## 9. LightGBM / scipy Packaging Risk

Known risks:

- LightGBM may require native binary or DLL handling.
- scipy may require native dependency handling.
- numpy/scipy/lightgbm can significantly increase packaged size.
- Hidden imports may be required.
- The packaged runtime can differ from the venv runtime.
- Some failures may appear only after exe execution, not during build.

If hidden import, DLL, or native dependency handling is needed, spec changes must be isolated into a follow-up Goal.

## 10. Rollback Policy

- If PyInstaller install fails and requirements were not changed, code rollback is not required.
- If the venv is polluted, recover by uninstalling the package or recreating the venv.
- If probe/spec files are later created and fail, revert that specific commit.
- Main app spec changes must be isolated in their own commit.
- Packaged build failure has no live trading or runtime impact.
- Existing Local AI registry artifacts remain preview artifacts and do not require deletion.

## 11. AI-ARCH-19-C Validation Checklist

AI-ARCH-19-C should verify:

- `python -m pip show pyinstaller`
- `python -m PyInstaller --version`
- `python -c "import PyInstaller; print(PyInstaller.__version__)"`
- `git diff -- requirements.txt`
- LightGBM/scipy import still works
- `app.learning.packaged_lightgbm_probe` still runs in the venv
- no spec file created
- no build executed
- no Router/UI/Execution changes

## 12. Decision Gate

GO:

- PyInstaller install succeeds.
- PyInstaller version is confirmed.
- requirements remain unchanged.
- LightGBM/scipy venv imports remain OK.
- packaged probe venv execution remains OK.
- no spec or build has been created yet.

WAIT:

- PyInstaller installs but version cannot be confirmed.
- requirements pin strategy remains unclear.
- build strategy remains unclear.

FAIL:

- PyInstaller install fails.
- Python execution breaks.
- requirements are polluted.
- LightGBM/scipy import breaks.
- Router/UI/Execution files are changed.

## 13. Future Goal Map

Recommended next sequence:

- AI-ARCH-19-C Controlled PyInstaller Install / Verify
- AI-ARCH-19-D Packaged LightGBM Probe Build
- AI-ARCH-19-E Main App PyInstaller Spec Planning
- AI-ARCH-19-F Main App Packaged Dependency Verification
- AI-ARCH-20 Local AI Shadow Training Loop Preview

## 14. Safety

- No live trading connection.
- No Router connection.
- No UI connection.
- No Execution connection.
- No Order connection.
- No Risk Guard bypass.
- No automatic training scheduler.
- No `active_model` auto-selection.
- No `model_auto_approved`.
- `submitted=0` principle remains in force.
- Packaged verification is dependency validation, not operational approval.

## 15. Current Disconnected State

The current packaging and Local AI learning pipeline remain disconnected from:

- UI
- Router
- Execution
- Order
- Risk Guard
- Runtime loop
- automatic training scheduler

