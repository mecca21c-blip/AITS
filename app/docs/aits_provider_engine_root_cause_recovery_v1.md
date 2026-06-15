# AITS Provider Engine Root-Cause Recovery v1

## 1. Purpose

- Record the root-cause recovery of recurring Provider/API/common-settings regressions.
- Preserve the ownership decisions that fixed the system instead of documenting symptom patches.
- Serve as a required reference for future Provider/API/Runtime/UI work by ChatGPT and Codex.
- Supplement `aits_provider_engine_state_contract_v1.md` with verified recovery outcomes.

## 2. Final Recovery Summary

- Startup restores the saved provider/model/key and resumes automatic connection verification.
- OpenAI and Gemini selection immediately applies the session Preview and starts API verification.
- The connection-check button performs manual revalidation only.
- The Save button owns persistence only.
- `정상연결` appears only after a real provider API response succeeds.
- Normal status copy is limited to `연결중`, `정상연결`, `연결실패`, and `연결확인 필요`.
- Routine key-status and key-source wording is hidden from the connection status surface.
- Key errors are reported through safe popup/error detail without exposing the key body.

## 3. Root Cause

- Deleted legacy `cb_ai_provider` references remained in the active path and caused `RuntimeError`.
- Hidden legacy combo, radio, and card signals could overwrite active provider state.
- Duplicate startup restore paths could overwrite a user selection or an established Preview state.
- Test helpers previously changed provider state as a side effect.
- Multiple Header and AI ENGINE writers could replace Preview with `미적용` or BASIC state.
- A `start_connection=False` restore path displayed the saved provider without starting API verification.
- Key existence and actual API connection success were mixed in user-facing status copy.
- Local function patches repeatedly regressed because active ownership and last-writer behavior were not fixed first.

## 4. Final Provider Contract

- Provider selection = session Preview application plus automatic connection verification.
- Connection-check button = manual revalidation of the currently selected provider.
- Save button = persistence of provider, model, key, and settings.
- Startup = restore saved provider/model/key, apply Preview, then start automatic verification.
- `정상연결` = a real provider API response completed successfully.
- `연결실패` = actual API verification failed.
- `연결중` = actual API verification is in progress.
- `연결확인 필요` = verification has not run, no usable key exists, or manual verification is needed.
- Preview application is display/session readiness, not live-trading or order application.

## 5. Final Ownership

- Active Provider UI: `aits_engine_choice_panel`.
- Provider selection entrypoint: `_select_ai_provider_for_session`.
- Header/AI ENGINE renderer: `_render_ai_engine_state`.
- Runtime proof: `RuntimeProof`, `EnginePanelProof`, and `ProviderConnectionProof`.
- Key body owner: `secrets.json`.
- Key presence flags: `prefs strategy.*_key_present`.
- Legacy `cb_ai_provider`: not an active provider owner.
- Basic Runtime Snapshot: diagnostic state that cannot overwrite Provider Preview.

## 6. Removed Or Disabled Legacy Paths

- Removed legacy `cb_ai_provider` from the active provider path.
- Disabled or delegated legacy combo, card, and radio signals to the single entrypoint.
- Removed or disabled persist-after-test helpers.
- Removed obsolete `_apply_selected_ai_engine` behavior from active ownership.
- Removed obsolete `_set_common_engine` behavior from active ownership.
- Removed duplicate startup connection schedulers.
- Delegated competing Header/AI ENGINE writes to `_render_ai_engine_state`.
- Prevented Save from reselecting the session provider or overwriting connection state.
- Kept compatibility paths non-owning and side-effect free where deletion was unsafe.

## 7. Provider State Layers

### Selected Provider

The provider most recently selected by the active UI for the current session.

### Saved Provider

The provider persisted at `prefs.json -> strategy.ai_provider` for restart restoration.

### Preview Provider

The provider/model displayed as ready for current-session AI Preview. It is not trading application.

### Connection Provider

The provider associated with the current or latest real API verification request and result.

### Actual Runtime Provider

The provider that actually produced an AI decision response in Orchestrator/runtime.

### Router Provider

Provider metadata supplied to DecisionRouter. It is not an order signal.

### Basic Runtime Snapshot

BASIC(Local) calculation/runtime diagnostics. It does not own OpenAI/Gemini Preview display.

## 8. Future Patch Rules

- Do not address Provider/API/Runtime/UI regressions by reinforcing one suspected function in isolation.
- First trace the active path, duplicate signals, legacy paths, final writer, and SSOT conflicts.
- If B repeatedly fails in A -> B -> C, fix A/B ownership instead of adding B1/B2/B3 helpers.
- When duplication is causal, prefer deletion, disabling, or delegation to one entrypoint.
- Do not add another Header or AI ENGINE card writer.
- Do not display `정상연결` based only on key, stored-secret, provider, or model existence.
- Do not call `save_settings` from provider selection or restore paths.
- Do not call Router, Execution, Order, or Risk Guard from provider selection or restore paths.
- Do not add save/apply side effects to connection-test handlers.
- Treat deleted Qt objects carefully: a Python attribute may survive while the underlying C++ object is gone.
- Confirm that a legacy widget is visible, alive, connected, and active before treating it as an owner.
- Keep key bodies out of prefs, logs, reports, status copy, and errors.

## 9. Verification Record

- Saved Gemini startup: `연결중` -> `정상연결`.
- GPT/OpenAI selection: `연결중` -> `정상연결`.
- Connection-check button: manual revalidation only.
- Save button: persistence only.
- Normal connection status excludes routine key-source wording.
- Live-trading, Router, Execution, Order, and Risk Guard behavior was unchanged.
- No PyInstaller build or packaged executable was run during this documentation Goal.

## 10. Required References

- State contract: `app/docs/aits_provider_engine_state_contract_v1.md`.
- Recovery record: `app/docs/aits_provider_engine_root_cause_recovery_v1.md`.
- Current operating rules: `AGENTS.md` and `docs/AITS_RULES_CURRENT.md`.
- Current ownership map: `docs/AITS_SOURCE_MAP_CURRENT.md`.
