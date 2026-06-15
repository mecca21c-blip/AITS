# AITS Current Source Map v2026-06

## 1. Purpose

This is the current source map for Codex/Agent to quickly understand AITS as of 2026-06-11.

It acts as an index and current summary for the official detailed documents under `app/docs`.

This file supersedes older source-map assumptions for agent work.

`docs/AITS_SOURCE_MAP_v2.md` is a detailed archival architecture map and is not the automatic current source map. `app/docs/aits_source_map_current.md` is an older app-internal reference document.

## 2. Official Architecture Summary

AITS is an AI Asset Management System.

High-level flow:

```text
Basic -> AI Engine -> Decision Router -> Execution Layer
```

Basic:

- Fact provider
- Candidate provider
- Risk feature provider
- Portfolio feature provider

AI Engine:

- GPT
- Gemini
- Local AI

Router:

- Validation
- Policy and risk checks

Execution:

- Executes only validated actions

AI must not place orders directly.

Execution is possible only after Router and Risk Guard validation.

The current AI-ARCH learning pipeline is not connected to the execution flow.

## 3. Current Core Runtime Flow

Key runtime components:

- `run.py`
- `AITSOrchestrator`
- `AIDecisionService`
- `DecisionRouter`
- `AIEngineProvider`
- `ExecutionBridge`
- `OrderAdapter`

Safety notes:

- AI does not directly submit orders.
- Execution must follow Router/Risk Guard validation.
- AI-ARCH learning modules are currently disconnected from runtime trading.

## 4. Official app/docs Document Index

Current official AI-ARCH and related design documents:

- `app/docs/aits_ai_architecture_v1.md`
- `app/docs/aits_local_ai_architecture_v1.md`
- `app/docs/aits_unified_trading_journal_schema_v1.md`
- `app/docs/aits_local_ai_model_registry_v1.md`
- `app/docs/aits_lightgbm_feature_schema_v1.md`
- `app/docs/aits_journal_sqlite_skeleton_v1.md`
- `app/docs/aits_journal_writer_preview_v1.md`
- `app/docs/aits_distillation_sample_builder_v1.md`
- `app/docs/aits_local_ai_shadow_evaluator_v1.md`
- `app/docs/aits_lightgbm_dataset_builder_preview_v1.md`
- `app/docs/aits_local_ai_evaluation_dashboard_preview_v1.md`
- `app/docs/aits_lightgbm_trainer_skeleton_v1.md`
- `app/docs/aits_model_artifact_registry_persistence_preview_v1.md`
- `app/docs/aits_lightgbm_dependency_gate_v1.md`
- `app/docs/aits_lightgbm_controlled_dependency_plan_v1.md`
- `app/docs/aits_lightgbm_controlled_install_verify_result_v1.md`
- `app/docs/aits_lightgbm_real_trainer_prototype_v1.md`
- `app/docs/aits_ai_reflection_event_schema_v1.md`
- `app/docs/aits_main_ai_output_contract_copy_fix_v1.md`
- `app/docs/aits_provider_engine_state_contract_v1.md`
- `app/docs/aits_provider_engine_root_cause_recovery_v1.md`

### Provider Engine State Ownership

The Provider Engine State Contract is the required reference for Provider/API/Engine UI changes.

State layers are distinct: Selected Provider, Saved Provider, Preview Provider, Connection Provider,
Actual Runtime Provider, Router Provider, and Basic Runtime Snapshot.

Active common-settings UI: `aits_engine_choice_panel`.

Active provider path:

```text
btn_engine_openai/gemini/local
-> _select_ai_provider_for_session
-> session Preview state + _render_ai_engine_state
-> _run_ai_startup_connection_check_async
-> ProviderConnectionProof
```

Compatibility helpers may delegate into this path, but they are not independent state owners.

Final Header and AI ENGINE card renderer: `_render_ai_engine_state`.

Known risk: Basic runtime snapshots, legacy helpers, or multiple writers can overwrite the current
OpenAI/Gemini Preview display. `_sync_basic_runtime_status_card` must preserve an active Preview.

### Provider Engine Final Ownership Map

- Active UI: `aits_engine_choice_panel`.
- Session selection entrypoint: `_select_ai_provider_for_session`.
- Final Header/AI ENGINE renderer: `_render_ai_engine_state`.
- Connection proof: `ProviderConnectionProof`.
- Runtime/panel proof: `RuntimeProof`, `EnginePanelProof`.
- Key body owner: `secrets.json`.
- Key presence flags: `prefs strategy.*_key_present`.
- Legacy `cb_ai_provider`: disabled/non-owner; deleted or hidden legacy widgets must not mutate provider state.
- Basic Runtime Snapshot: diagnostics only and cannot overwrite Provider Preview.

Removed or disabled legacy paths include duplicate provider combo/card/radio signals, persist-after-test behavior, obsolete apply/common-engine helpers, duplicate startup schedulers, and direct competing Header writers. Remaining compatibility paths must delegate to the single entrypoint and renderer.

Startup flow:

```text
saved provider/key/model
-> _select_ai_provider_for_session(reason=startup_restore, start_connection=True)
-> 연결중
-> actual provider API proof
-> 정상연결 / 연결실패
```

User selection flow:

```text
aits_engine_choice_panel click
-> _select_ai_provider_for_session(reason=provider_panel_click, start_connection=True)
-> Preview provider/model render
-> actual provider API proof
-> 정상연결 / 연결실패
```

The Save button persists settings only. Manual connection buttons revalidate only. Neither flow invokes Router, Execution, Order, or Risk Guard.

## 5. Local AI Learning Pipeline File Map

`app/storage/journal_store.py`

- Journal SQLite skeleton
- Preview writer
- sanitize / validate / index / append / load / list helpers

`app/learning/distillation_sample_builder.py`

- GPT/Gemini teacher sample builder
- JSONL export

`app/learning/local_ai_shadow_evaluator.py`

- teacher vs local_ai student output comparison
- `agreement_score`
- severity
- JSONL export

`app/learning/lightgbm_dataset_builder.py`

- Journal record to LightGBM dataset row
- feature / label / target extraction
- leakage filtering
- JSONL / CSV export

`app/learning/local_ai_evaluation_dashboard.py`

- distillation / shadow / dataset summary
- readiness judgement
- JSON / Markdown report export

`app/learning/lightgbm_trainer_skeleton.py`

- dry-run trainer summary
- artifact manifest skeleton
- evaluation report skeleton
- model registry entry skeleton

`app/learning/model_registry_store.py`

- `data/local_ai_registry` persistence
- `registry_index.json`
- `active_model.json` preview pointer
- artifact JSON save/load

`app/learning/lightgbm_dependency_gate.py`

- LightGBM import/version/dependency readiness report

`app/learning/lightgbm_real_trainer.py`

- real LightGBM prototype train/predict/save/load
- small in-memory dataset only
- `model_auto_approved=False`
- no automatic active model setting

## 6. Data Path Map

Development runtime data root: `C:\AITS\data`

Packaged runtime data root: `%LOCALAPPDATA%\AITS\data`

`data/aits_journal.sqlite3`

- Unified Trading Journal SQLite database

`data/local_ai_registry/`

- model registry preview persistence

`data/secrets.json`

- secret key bodies

`data/secret.bin`

- secret-related file

`prefs.json`

- general settings
- provider
- key_present flags
- UI state

Safety notes:

- secrets files must not be committed.
- `local_ai_registry` artifact policy needs a future controlled decision before real artifact retention is expanded.

## 7. Completed AI-ARCH Stages

- AI-ARCH-01: AITS AI Architecture
- AI-ARCH-02: Local AI Architecture
- AI-ARCH-03: Unified Trading Journal Schema
- AI-ARCH-04: Local AI Model Registry
- AI-ARCH-05: LightGBM Feature Schema
- AI-ARCH-06: Journal SQLite Skeleton
- AI-ARCH-07: Journal Writer Preview
- AI-ARCH-08: GPT/Gemini Distillation Sample Builder
- AI-ARCH-09: Local AI Shadow Evaluator
- AI-ARCH-10: LightGBM Dataset Builder Preview
- AI-ARCH-11: Local AI Evaluation Dashboard Preview
- AI-ARCH-12: LightGBM Trainer Skeleton
- AI-ARCH-13: Model Artifact / Registry Persistence Preview
- AI-ARCH-14: LightGBM Dependency Gate
- AI-ARCH-14-B: Controlled LightGBM Dependency Plan
- AI-ARCH-15: Controlled LightGBM Install / Verify
- AI-ARCH-16: LightGBM Real Trainer Prototype
- AI-ARCH-17: Trainer Evaluation Report Fill
- AI-ARCH-18: Model Registry Real Artifact Integration
- AI-ARCH-15-C: LightGBM Requirements Pin Commit
- AI-ARCH-19 series: Packaged dependency, probe, main-app build, smoke, and runtime-path verification
- AI-REFLECT-01: AI Reflection Event Schema
- UI-MAIN-01: Main AI Output Contract and Copy Fix

## 8. Current Dependency State

- LightGBM `4.6.0` is installed in the current development venv.
- scipy `1.17.1` is installed as a dependency.
- `requirements.txt` pins `lightgbm==4.6.0`; scipy remains transitive.
- PyInstaller `6.20.0` was installed in the development venv without a requirements pin.
- Independent packaged LightGBM/scipy/trainer probe verification passed.
- Main-app onedir build and startup smoke were demonstrated, and packaged writable data was moved to `%LOCALAPPDATA%\AITS\data`.
- The packaged application is not a final distribution build. Packaging is currently HOLD.

## 9. Current Disconnected State

- Journal Writer is not automatically connected to Router runtime.
- Dataset Builder does not run automatic training.
- Real Trainer is not an automatic training scheduler.
- Model Registry `active_model` is a preview pointer.
- Reflection Event runtime/UI/Journal connection: none
- Local AI learning pipeline UI connection: none
- Execution connection: none
- Order connection: none
- RiskGuard bypass: none

## 10. Recommended Next Work

- Continue development-mode UI readiness and behavior verification.
- AI-REFLECT-02: Reflection Event Preview Builder.
- Add Reflection UI/Journal integration only through separate controlled Goals.
- Keep packaging HOLD until application functionality is ready for another packaging Goal.
