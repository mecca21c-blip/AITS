# AITS Provider Engine State Contract v1

## 1. Purpose
- Prevent recurring API key, provider, Preview, and runtime display regressions.
- Define the reference contract for all future provider-related patches.
- Give ChatGPT and Codex one shared, reviewable structure.
- Keep UI Preview readiness separate from runtime, Router, and trading behavior.

## 2. Problem Statement
- Provider state has several owners: selected, saved, Preview, connection, runtime, and Router.
- Header and AI ENGINE card values have multiple writers.
- Basic runtime snapshots can overwrite OpenAI/Gemini Preview displays.
- Legacy and current common-settings UI generations coexist.
- Automatic and manual connection checks overlap.
- Save and session Preview application have been confused.
- Function-level fixes regress because ownership and last-writer rules are not system-wide.

## 3. Provider State Layers
### Selected Provider
- Provider most recently selected in the active UI.
- Current example: `_selected_ai_provider`.
- Session-only; it does not imply persistence or successful connection.

### Saved Provider
- Persistent provider at `prefs.json -> strategy.ai_provider`.
- Written by the settings save flow and used for restart restoration.

### Preview Provider
- Provider prepared and displayed for AI Runtime Preview in the current session.
- Current examples: `_applied_ai_provider`, `_applied_ai_model`, `_applied_ai_is_preview`.
- Preview is not live-trading application and does not enable orders.

### Connection Provider
- Provider associated with the latest API connection result.
- Current examples: `_last_ai_connection_provider`, `_last_ai_connection_status`,
  `_last_ai_connection_source`.
- Key sources: `ui_input`, `pending_verified`, `stored_secret`, `environment`.

### Actual Runtime Provider
- Provider actually used by Orchestrator or `AIEngineProvider` for an AI decision call.
- It may differ from Preview and requires runtime evidence.

### Router Provider
- Provider passed to `DecisionRouter`, derived from `strategy.ai_provider` or Orchestrator meta.
- It is routing/readiness metadata, not an order signal.

### Basic Runtime Snapshot
- BASIC(Local) calculation/runtime diagnostic state.
- It is not OpenAI/Gemini Preview state and must not overwrite that Preview card.

## 4. Provider Action Contract
### Provider Selection
- Change Selected Provider and visible Preview Provider/model immediately.
- If a usable key exists, begin connection verification or show that verification is required.
- Do not save provider/model/key and do not invoke Router, Execution, orders, or live trading.

### Connection Check Button
- Manually recheck API communication for the selected provider.
- Update connection/session display only.
- Do not save, persist selection, or apply to trading runtime.

### Save Button
- Persist provider, model, key, and settings for the next start.
- Preserve or refresh current Preview display.
- It is not an engine-application or trading-start button.

### Restart
- Restore Saved Provider, model, key presence, and the matching Preview display.
- Automatic API communication is a separate explicit policy.
- Without automatic communication, show `저장됨 · 연결 확인 필요`.

## 5. Key Ownership Contract
- API key bodies belong only in `secrets.json`.
- `prefs.json` must contain no key body; it stores `key_present` flags.
- Never expose key bodies in inputs, logs, reports, or errors.
- A saved key is displayed as the 20-bullet sentinel `●●●●●●●●●●●●●●●●●●●●`.
- The sentinel is not a key; saving it preserves the existing secret.
- Environment keys are test fallbacks and must not be saved automatically.
- Environment success must say `환경변수 Key 사용 · 저장된 Key 아님`.

## 6. Active UI Ownership
- Final common-settings provider UI: `aits_engine_choice_panel`.
- Active buttons: `btn_engine_openai`, `btn_engine_gemini`, `btn_engine_local`.
- Active key fields:
  - `ed_openai_key_new` rebound to `self.ed_openai_key`.
  - `ed_gemini_key_new` rebound to `self.ed_gemini_key`.
- Legacy `ed_ai_api_key` is not an owner and must not overwrite active fields.

## 7. Active Provider Path
```text
btn_engine_openai / btn_engine_gemini / btn_engine_local
-> _sync_engine_choice_panel
-> _set_ai_provider_ui_active
-> _activate_ai_provider_preview
-> _apply_saved_ai_preview
-> _run_ai_startup_connection_check_async
```
- This is the active path.
- Never assume a legacy helper is active without checking visibility and signal connections.

## 8. Save, Restore, And Connection Flow
### Save
```text
btn_save
-> _on_save_settings
-> _apply_settings_patch
-> prefs.save_settings_patch
-> prefs.save_settings
-> _sync_secrets_from_payload
```

### Restore
```text
load_settings
-> prefs + secrets + environment merge
-> _sync_ai_provider_ui_from_settings
-> _restore_ai_key_masking_from_settings
-> _restore_api_keys_after_ui_ready
-> _activate_ai_provider_preview
```

### Connection
- Automatic: `_run_ai_startup_connection_check_async`.
- Manual: `_on_test_gpt`, `_on_test_gemini`.
- Shared: `_resolve_ai_test_secret`, `_record_ai_connection_result`.
- Result signal: `_ai_preview_connection_finished`.
- Request token and selected-provider guards block stale result overwrite.

## 9. Header And AI ENGINE Writer Ownership
- `_render_ai_engine_state`: final top summary and AI ENGINE card renderer.
- `_update_engine_status_box`: large runtime/status box writer.
- `_get_aits_engine_ssot`: currently prioritizes Saved Provider.
- `_sync_basic_runtime_status_card`: Basic snapshot writer; requires a Preview guard.
- `_build_runtime_ui_snapshot_bundle`: Basic/runtime diagnostics source, not Preview ownership.

## 10. Single Renderer Rule
- `_render_ai_engine_state` owns final Header and AI ENGINE card output.
- Do not add new direct writers for those labels.
- Other helpers update state and call the renderer.
- Basic helpers must not set Selected/Preview to Basic during OpenAI/Gemini Preview.
- `미적용` is allowed only with no provider/model/key or explicit Basic/default selection.
- The large runtime box may show actual runtime only when labeled separately from Preview.

## 11. Display Contract
### OpenAI/Gemini Selected With Key
- 선택 엔진: `Gemini`.
- Preview 엔진: `Gemini · gemini-2.5-flash`.
- 적용: `Preview`.
- 모델: `gemini-2.5-flash`.
- 상태: `연결 확인 중`, `저장된 Key 확인됨`, or `연결 실패`.

### Immediately After Restart
- 선택 엔진: saved provider.
- Preview 엔진: saved provider and model.
- 적용: `Preview`.
- 상태: `저장됨 · 연결 확인 필요` until verified.

### Basic
- `Basic 계산 엔진`.
- `AI 판단 없음`.
- `주문 없음`.

Forbidden claims: `실거래 적용`, `주문 가능`, `자동매매 실행`, `AI 직접 주문`.

## 12. Conflict Rules
- Never conflate selected, saved, Preview, actual runtime, or Router provider.
- Do not duplicate automatic and manual API test implementations.
- Do not treat legacy helpers or hidden widgets as active owners.
- Do not infer key absence from key-field text; check stored-secret existence.
- Basic snapshots must not overwrite the Preview card.
- Trace active signals and final writers before every provider patch.
- `strategy.ai_provider` is Saved Provider SSOT, not universal runtime SSOT.

## 13. Simplification Plan
Next Goal: `AITS-ENGINE-STATE-02 Provider Engine Single Renderer Patch`.
- Consolidate provider session-state helpers in `app_gui.py`.
- Fix `_render_ai_engine_state` as final Header/Card owner.
- Add a provider-aware guard to `_sync_basic_runtime_status_card`.
- Unify automatic/manual connection checks behind one internal helper.
- Disconnect legacy provider/key writers from the active UI.
- Review `config_tabs.py` `StrategyConfig()` fallbacks to preserve Saved Provider.
- Keep Orchestrator, Router, Execution, Order, and Risk Guard behavior unchanged.

## 14. AITS-ENGINE-STATE-02 Acceptance Criteria
- Provider selection immediately displays matching Preview provider/model.
- Session Preview remains without pressing Save.
- Restart restores Saved Provider, model, and 20-bullet mask.
- Basic refresh cannot overwrite OpenAI/Gemini Preview.
- Connection state correctly moves through checking, verified, and failed.
- Automatic/manual checks produce the same normalized result state.
- No key body is exposed or written to prefs.
- Router, Execution, Order, and Risk Guard remain unchanged.
- `submitted=0` remains true.

## 15. ChatGPT Verification Summary
- Layers: Selected is current UI choice; Saved is `strategy.ai_provider`; Preview is session
  readiness/display; Connection is provider-specific API status; Actual Runtime performed the
  decision call; Router Provider is routing metadata; Basic Snapshot is diagnostics only.
- Active path: button -> `_sync_engine_choice_panel` -> `_set_ai_provider_ui_active` ->
  `_activate_ai_provider_preview` -> `_apply_saved_ai_preview` -> async connection check.
- Writer ownership: `_render_ai_engine_state` owns Header/Card. Basic and runtime helpers update
  state but cannot replace OpenAI/Gemini Preview ownership.
- Next patch: enforce the single renderer, guard Basic refresh, unify connection results, and
  preserve provider through `config_tabs.py` fallbacks without touching execution layers.
