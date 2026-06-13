# AITS Codex Operating Rules

AITS is a Goal-driven AI Asset Management System.

This file is the automatic Codex entry point. Detailed rules and architecture live in:

- `docs/AITS_RULES_CURRENT.md`
- `docs/AITS_SOURCE_MAP_CURRENT.md`

Precedence: current Goal > this file > AITS_RULES_CURRENT > AITS_SOURCE_MAP_CURRENT > archive documents.

## Token-Safe Mode

- Do not read large files in full.
- For `app/ui/app_gui.py`, use `rg` first, then read only 80-150 lines around relevant anchors.
- Do not perform full-repository audits unless the Goal explicitly requires one.
- Exclude `build/`, `dist/`, `__pycache__/`, logs, archives, and runtime data from routine searches.
- Do not repeat searches or file reads when the result is already known.
- Read detailed `app/docs` files only when directly relevant to the current Goal.

## Goal Scope

- The patch unit is the Goal, not a file.
- Modify only files directly required to complete the current Goal.
- No unrelated cleanup, refactoring, formatting, or architecture changes.
- Preserve existing behavior unless the Goal explicitly changes it.
- Work with existing dirty files; do not revert or clean unrelated changes.

## Trading Safety

Without explicit Goal approval, do not modify:

- `app/services/decision_router.py`
- `app/services/aits_orchestrator.py`
- `app/services/execution_bridge.py`
- `app/services/order_adapter.py`
- `app/services/order_service.py`
- Risk Guard or live-trading paths

AI must not place orders directly. Keep Router, Risk Guard, and Execution boundaries intact. Maintain `submitted=0` unless a separate live-execution Goal explicitly authorizes otherwise.

## Packaging HOLD

- Packaging work is currently HOLD.
- Do not run PyInstaller builds or packaged executables unless the Goal is explicitly a packaging Goal.
- Do not modify specs, requirements, or packaging assets outside such a Goal.
- Build and smoke outputs are never commit targets.

## Runtime Data And Secrets

- Never commit `secrets.json`, `secret.bin`, `prefs.json`, journal databases, `local_ai_registry`, API keys, logs, or runtime artifacts.
- Packaged writable data belongs under `%LOCALAPPDATA%\AITS\data`.
- Development writable data belongs under `C:\AITS\data`.
- Do not inspect or expose secret bodies during validation or reporting.

## UI And AI Copy

- Basic Engine is not AI; it is calculation and fact-provider logic.
- Without an explicit AI Output Contract, do not present output as AI judgement, confidence, scenario, or ETA.
- Basic/fallback output must remain calculation-based reference information and not an order signal.
- Reflection Events are review candidates, not confirmed AI failures or order signals.

## Provider Engine State

- Before Provider/API/Engine UI work, read `app/docs/aits_provider_engine_state_contract_v1.md`.
- Keep selected, saved, Preview, connection, actual runtime, Router, and Basic provider states distinct.
- Do not add another Header or AI ENGINE card writer; prefer `_render_ai_engine_state` as the final renderer.
- Ensure `_sync_basic_runtime_status_card` cannot overwrite an OpenAI/Gemini Preview state.
- Provider selection changes session Preview; it does not save settings.
- Connection checks manually revalidate API access; they do not persist or apply settings.
- The Save button owns persistence. Preview application is not live-trading or order application.

## Validation

Scale validation to the Goal:

- Documentation-only Goal: existence, line count, keyword, and scoped diff checks.
- UI copy or narrow Python Goal: `py_compile` by default.
- Startup, GUI smoke, provider calls, build, and packaged execution only when explicitly required.
- Never trigger API-key tests, live orders, or trading controls as incidental validation.

## Git

- Never use `git add .`.
- Stage only explicitly allowed files by path.
- Prefer path-limited `git status` and `git diff`; avoid repeated full diffs.
- Do not stage `build/`, `dist/`, `__pycache__/`, logs, runtime data, or unrelated dirty files.
- Commit only when the Goal requests it or the user explicitly approves it.

## Reporting

Keep completion reports concise. Prioritize:

1. Goal
2. Created or modified files
3. Main changes
4. Validation result
5. Prohibited-layer modification status
6. Packaging execution status
7. Commit hash
8. Remaining issues

## Current SSOT

- `strategy.ai_provider`
- `orchestrator.execution_mode`
- `basic_config`
- `managed_pool_rows`

Do not create duplicate sources of truth.
