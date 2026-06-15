# AITS Current Agent Rules v2026-06

## 1. Purpose

The repository-root `AGENTS.md` is the automatic Codex operating entry point. This document provides the detailed safety and architecture rules referenced by that entry point.

It does not replace the official detailed documents under `app/docs`. It is the current working rules summary for safe Goal execution.

Use this document at the start of new work to confirm safety boundaries, current architecture assumptions, and reporting expectations.

## 2. Project Definition

AITS is a Python + PySide6 AI trading and AI asset management system.

The final target is an AI Asset Management System, not a simple auto-trading bot.

Current phase:

- Local AI learning pipeline buildout
- Preview / Shadow / Architecture validation
- LightGBM prototype validation
- Main UI semantic-contract stabilization
- Reflection schema design

AITS is not currently in a live automated trading expansion phase.
Packaging work is currently HOLD while development-mode functionality and UI readiness are improved.

## 3. Roles

User:

- Final decision maker
- Execution owner
- Screenshot provider when needed
- Feedback provider

ChatGPT:

- System designer
- Goal designer
- Codex instruction author
- Risk assessor

Codex/Agent:

- Code modification
- Document creation
- Validation execution
- Log summary
- Git commit

## 4. Goal-Driven Development Rules

The patch unit is a Goal, not a file.

Every Goal should include:

- current state
- target state
- completion conditions

Do not perform unrelated refactoring.

Limit the change scope to areas directly required for Goal completion.

## 5. Live Trading Safety Rules

The following safety rules are mandatory:

- Keep `submitted=0` unless a separate explicit live execution Goal approves otherwise.
- AI must not place orders directly.
- Do not bypass Risk Guard.
- Do not bypass Execution Layer.
- Do not modify OrderAdapter, OrderService, or ExecutionBridge without separate explicit approval.
- Do not modify Router action logic without separate explicit approval.
- Do not connect new work to Live Trading paths.
- Prefer Preview / Shadow / Dry-run before any runtime action.

## 6. AI Architecture Rules

Basic Engine is not AI.

Basic Engine is a Fact Provider, calculator, and candidate compression layer.

GPT, Gemini, and Local AI are AI Engine Slots.

Local AI is composed of:

- Memory
- Journal
- ML Engine
- Reason Runtime

LightGBM is one component of the Local AI ML Engine.

LightGBM does not replace the Reason Runtime.

LightGBM scores are not order signals.

Model Registry `active_model` is a preview pointer and is not live approval.

## 7. Prohibited Narratives / Implementations

Do not present Basic calculations as AI judgement.

Do not present rule-based results as AI Narrative.

Do not generate Intent, Scenario, or Why without an AI Output Contract.

Do not create fake AI Narrative.

Do not store preview results as executed results.

Do not store shadow results as live results.

## 8. Storage / Security Rules

Do not store API keys in learning artifacts, journal records, model artifacts, reports, or logs.

Do not store:

- Upbit secrets
- OpenAI/Gemini key bodies
- account secrets
- raw private account details
- raw order secrets
- uncontrolled raw Journal dumps
- bulk raw OHLCV arrays

Maintain sanitize-before-record principles for `record_json`.

Secrets belong in the secrets storage layer, such as `secrets.json`.

Prefs should store general settings, provider state, `key_present` flags, and UI state, not key bodies.

## 9. AI-ARCH Work Rules

Prefer official detailed documents under `app/docs`.

`app/learning` is dedicated to the Local AI learning pipeline.

`app/storage/journal_store.py` is the Journal SQLite skeleton and preview writer layer.

`data/local_ai_registry` is the model registry preview persistence area.

LightGBM `4.6.0` is installed and pinned in `requirements.txt`.

PyInstaller and packaged dependency/main-app smoke verification were performed, but the packaged application is not a final distribution build. Packaging work is currently HOLD.

AI-REFLECT-01 defined Reflection Events as review and learning candidates, not order signals.

UI-MAIN-01 separated explicit AI Output Contract copy from Basic/fallback calculation copy.

## 10. Provider Engine Root-Cause Rule

Provider/API/Runtime/UI regressions must be handled by tracing ownership, not by stacking symptom helpers. Before editing, identify the active signal path, duplicate signals, hidden legacy paths, the final UI writer, and conflicting sources of truth. When a repeated A -> B -> C failure is located at B, repair A/B ownership instead of adding B1/B2/B3 helpers.

Keep these seven layers distinct:

- Selected Provider
- Saved Provider
- Preview Provider
- Connection Provider
- Actual Runtime Provider
- Router Provider
- Basic Runtime Snapshot

Final action contract:

- Provider selection applies the current session Preview and starts automatic API verification when a usable key exists.
- The connection-check button manually revalidates the selected provider and does not save or apply settings.
- The Save button persists provider, model, key, and settings only.
- Startup restores the saved provider/model/key, applies Preview, and resumes automatic verification.
- `정상연결` is allowed only after a real provider API response succeeds.
- `연결중`, `정상연결`, `연결실패`, and `연결확인 필요` are the only normal provider status labels.
- Routine key-source and key-presence copy stays out of the provider status surface. Key errors belong in safe popup/error detail.
- Preview application never means live-trading or order application.

Legacy and writer rules:

- Remove, disable, or delegate duplicate combo/radio/card signals to the single provider entrypoint.
- Deleted or hidden Qt widgets are not active owners; verify object lifetime before accessing legacy attributes.
- Do not add another Header or AI ENGINE writer. `_render_ai_engine_state` is the final renderer.
- Basic runtime snapshots must not overwrite an OpenAI/Gemini Preview.
- Do not mark a provider connected merely because a key, stored secret, or model exists.
- Do not call `save_settings` from provider selection or restore paths.
- Do not add persistence/apply side effects to connection-test handlers.
- Do not call Router, Execution, Order, or Risk Guard from provider selection or restore paths.

Detailed recovery record: `app/docs/aits_provider_engine_root_cause_recovery_v1.md`.

## 11. Communication / Reporting Format

Completion reports should focus on:

1. Goal
2. Created/modified files
3. Major changes
4. Validation results
5. Prohibited layer modification status
6. requirements/dependency modification status
7. Git commit hash
8. Remaining issues

Do not put screenshot requests inside Codex patch instructions.

User-facing manual work should be requested by ChatGPT outside code blocks.

Use `git add` with explicit allowed file paths only. Never use `git add .` in this repository.

Validation must be proportional to the Goal. Documentation-only Goals may use file existence, keyword, line-count, and scoped-diff checks without startup or build execution.

## 12. Currently Prohibited Layers

Do not modify the following unless a Goal explicitly allows it:

- `app/ui/app_gui.py`
- `app/services/decision_router.py`
- `app/services/aits_orchestrator.py`
- `app/services/execution_bridge.py`
- `app/services/order_adapter.py`
- `app/services/order_service.py`
- Risk Guard related files

Exceptions require explicit Goal authorization.

## 13. Current Candidate Next Work

- Development-mode UI readiness and safety-copy stabilization
- AI-REFLECT-02 Reflection Event Preview Builder
- Reflection UI and Journal integration only through separate controlled Goals
- Resume packaging only through an explicit packaging Goal after HOLD is lifted
