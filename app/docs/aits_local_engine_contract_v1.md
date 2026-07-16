# AITS Local Engine Contract v1

## 1. Purpose

- Define the user-facing meaning and internal boundaries of the AITS LOCAL engine.
- Remove confusion caused by `BASIC(Local)`, BASIC, local, Ollama, qwen, and mistral labels.
- Establish the reference contract for future common-settings LOCAL UI cleanup.
- Keep user-facing engine identity separate from internal provider codes, runtime snapshots, and model diagnostics.

## 2. Final User-Facing Engine Choices

The engine selector exposes exactly three choices:

- `LOCAL`
- `GPT`
- `GEMINI`

`BASIC`, `BASIC(Local)`, Ollama, qwen, and mistral are not user-facing engine choices.

## 3. LOCAL Engine Definition

LOCAL is the default internal AITS engine that operates without an external AI API.

- It is available as part of the application without OpenAI or Gemini credentials.
- It consumes accumulated market data, performance history, Reflection candidates, calculated scores, and learning candidates according to approved policy.
- It must remain usable when no external provider is configured.
- It supports Shadow and Preview judgement assistance.
- It does not place orders directly.
- It does not bypass DecisionRouter, Execution, Order, or RiskGuard boundaries.
- It does not convert a Preview judgement into live-trading approval.
- It is intended to evolve through validated data accumulation and Reflection-based review.

The current implementation includes rule-based and calculation-oriented local behavior. This contract defines the product identity and future boundary; it does not claim that automatic learning or automatic model activation already exists.

## 4. BASIC Internal Layer Definition

BASIC is an internal calculation, score, and fact-provider layer within LOCAL.

- BASIC supplies reference values, candidate scores, facts, and runtime diagnostics.
- BASIC is not an engine name that users select.
- User UI must not expose `BASIC` or `BASIC(Local)` as the LOCAL engine identity.
- BASIC may assist LOCAL judgement but is not itself an AI Output Contract.
- BASIC output remains calculation-based reference information and is not an order signal.
- Internal logs, traces, tests, and developer diagnostics may retain `basic` when required to describe the implementation layer.

## 5. qwen, mistral, And Ollama Policy

- qwen, mistral, and Ollama are not Provider choices.
- They may remain internal implementation candidates, runtime adapters, benchmarks, or historical development artifacts.
- The normal user flow must not ask users to choose among qwen, mistral, or Ollama.
- Internal model identifiers may appear only in developer diagnostics or a deliberately hidden diagnostic surface.
- General user UI must not display `Ollama Runtime`, `model=mistral:latest`, qwen, mistral, or similar implementation copy.
- Changing an internal model must not redefine the user-facing engine from LOCAL to that model name.

## 6. LOCAL Settings Contract

LOCAL settings configure data-processing and review policy, not a local model picker.

### Data Usage Level

- Conservative: prioritize verified and stable data.
- Standard: balance recent data with accumulated review history.
- Active: reflect recent patterns and opportunity-cost evidence more quickly.

### Reflection Data Usage

- Stop-loss and take-profit review candidates.
- Missed exit timing candidates.
- Missed rotation opportunity candidates.
- Good waiting decisions.
- Risk avoidance decisions.

Reflection records remain review candidates. They are not confirmed AI failures or direct training labels until `label_ready` requirements are satisfied.

### Learning Application Policy

- Observe only.
- Apply to Preview.
- Apply after validation.
- Never set or activate an `active_model` automatically from these settings.

### Recent Data Weight

- Low.
- Standard.
- High.

### Safety Policy

- No direct live order execution.
- No Router or RiskGuard bypass.
- No unverified learning application.
- No automatic live-trading approval.

## 7. API Connection Contract

- GPT and GEMINI are external API providers and require real API connection verification.
- GPT/GEMINI show `정상연결` only after a real API response succeeds.
- LOCAL is not an external API connection target.
- Selecting LOCAL must not start OpenAI, Gemini, Ollama, or other external API verification.
- Reusing `연결중` or `정상연결` for LOCAL can incorrectly imply an external connection.
- Candidate LOCAL status copy includes `LOCAL 활성`, `내부 엔진 준비됨`, `API 없음`, and `Shadow/Preview`.
- The final compact LOCAL copy is selected in the follow-up UI Goal.

## 8. Provider State Layer Map

The current code mixes `basic` and `local`. The table records the implementation truth and the target user contract.

| State layer | Current code values or source | Contract and cleanup direction |
| --- | --- | --- |
| Selected Provider | `_selected_ai_provider` commonly uses `basic`; panel visual key uses `local` | User sees LOCAL; internal value should be normalized consistently in a later patch |
| Saved Provider | `strategy.ai_provider`; existing code accepts `local` and `basic` | Persist one canonical LOCAL code after compatibility review; never expose BASIC as the saved user choice |
| Preview Provider | `_applied_ai_provider` can be `basic`; `_applied_ai_is_preview=True` | Render LOCAL Preview without external API status semantics |
| Connection Provider | External providers use GPT/OpenAI or Gemini; BASIC currently receives a local status value | LOCAL is not an API Connection Provider; keep external connection proof separate |
| Actual Runtime Provider | `LocalProvider.name = "local"`; registry fallback is `local` | LOCAL is the user-facing runtime family; actual runtime evidence remains separate from Preview |
| Router Provider | DecisionRouter and Orchestrator normalize `basic`/`local` to `local` | Preserve Router safety boundary; LOCAL metadata is not an order signal |
| Local/BASIC Runtime Snapshot | `_build_basic_runtime_ui_status`, `_sync_basic_runtime_status_card`, and related bundles expose `BASIC(Local)`, Ollama, and model names | Keep diagnostics internal and prevent them from owning or overwriting the LOCAL user-facing card |

Current normalization examples:

- UI engine SSOT currently returns `basic` for `local`, `basic`, and related aliases.
- `AIEngineProvider` maps `basic`, `local`, and `localprovider` to `LocalProvider` behavior.
- DecisionRouter and Orchestrator normalize `basic` and `local` to `local`.
- The active panel uses a `local` visual key while some session state uses `basic`.

This mixed representation is a compatibility fact, not the desired user-facing vocabulary. Canonical internal normalization requires a separate controlled code Goal.

## 9. Current Ambiguity To Remove

The following expressions are cleanup targets in normal user UI:

- `BASIC(Local)`
- `BASIC`
- `BASIC 계산 엔진`
- `Ollama Runtime`
- `model=mistral:latest`
- `qwen`
- `mistral`
- `display-only`

These terms may remain where necessary in internal logs, traces, tests, compatibility parsing, or developer-only diagnostics.

Confirmed current exposure areas include:

- `aits_engine_choice_panel` LOCAL button and description.
- LOCAL settings box and runtime-ready controls.
- `_format_runtime_ui_snapshot_text` output.
- `_sync_basic_runtime_status_card` compact/detail output.
- Legacy local model combo and install controls.
- Runtime snapshot/timeline/incident diagnostics with default mistral or qwen identifiers.

## 10. Next Patch Criteria

Follow-up Goal: `AITS-LOCAL-ENGINE-02 Local Engine UI Copy & Ownership Cleanup`.

Acceptance criteria:

- Common-settings engine cards display only LOCAL, GPT, and GEMINI.
- `BASIC(Local)` is removed from normal user UI.
- Ollama, mistral, and qwen are removed from the normal LOCAL surface.
- LOCAL selection performs no external API connection verification.
- LOCAL displays `LOCAL 활성` or `내부 엔진 준비됨`-style state.
- Shadow analysis copy differs by provider family:
  - LOCAL: `주문 없음 · API 없음`.
  - GPT/GEMINI: `주문 없음 · API 호출 가능`.
- BASIC runtime diagnostics cannot overwrite the LOCAL/GPT/GEMINI provider card.
- Router, Execution, Order, and RiskGuard remain unchanged.

## 11. ChatGPT Verification Summary

- User-facing engines are LOCAL, GPT, and GEMINI only.
- BASIC is an internal calculation, score, and fact-provider layer under LOCAL.
- LOCAL is the default AITS engine that operates without an external API.
- LOCAL settings govern data processing, Reflection usage, and validated learning-application policy rather than model selection.
- qwen, mistral, and Ollama are not user choices.
- The follow-up UI patch removes `BASIC(Local)` and internal model/runtime names from normal user surfaces.
- Preview remains separate from live trading, and all Router/RiskGuard/Execution boundaries remain intact.

## 12. LOCAL-ENGINE-USER-FACING-COPY-FIX-01 Update

- Normal user-facing copy should describe LOCAL as internal calculation-based analysis that works without external AI API credentials.
- BASIC remains an internal implementation term for calculation, scoring, summaries, and diagnostics; it should not appear as an independent user-selectable engine.
- Ollama remains an optional local LLM runtime and diagnostic/inference-gate target; the normal LOCAL refresh path must not imply that Ollama inference is automatically active.
- LOCAL data policy copy describes retention, review-summary preparation, and validation-before-application policy. It must not imply that automatic deep learning or active training is currently running.
- LOCAL output remains reference/display/shadow-oriented and must keep `submitted=0`, `order_allowed=False`, and `real_order=False`.

## 13. LOCAL-OLLAMA-NONBLOCKING-FIX-01 Update

- The manual LOCAL/Ollama LLM diagnostic button runs its `/api/tags` and `/api/generate` checks in a Qt worker thread so the UI thread does not wait on the 60 second diagnostic timeout.
- This diagnostic path is not the normal LOCAL analysis path. Normal LOCAL analysis remains the internal calculation-based payload path and does not promote Ollama to an active provider.
- Diagnostic results are displayed as readiness/test feedback only. They must not publish `ai.reco.updated`, create `AISnapshotStore` entries, update detail-chart AI snapshots, or write `TradeLogShadowJournal` decision records.

## 14. Internal LOCAL_ENGINE And Data Recovery v1

- `AITS_LOCAL_ENGINE` is an in-process decision candidate engine, not an Ollama
  HTTP server, CLI process, or bundled model runtime.
- Its candidate schema is `aits_local_engine_decision_candidate.v1` and includes
  action, calibrated-confidence status, risk, escalation, ETA, invalidation,
  structured evidence, Korean reason, teacher reference, and training provenance.
- Default policy remains `safe_for_live_decision=false` and
  `live_decision_enabled=false`. Contract availability does not grant live authority.
- GPT/Gemini are teacher and escalation sources. Their outputs become learning
  evidence only after observed outcome, curation, and feature quality gates.
- Ollama is developer-only/manual experimental infrastructure. Automatic live
  generation remains blocked by the developer-only gate and disabled defaults.
- Source outcome JSONL is preserved. Corrupt derived datasets, registry, and
  calibration outputs are quarantined and regenerated through the offline pipeline.
- See `app/docs/aits_internal_local_engine_v1.md` for the complete contract.
- Failure, timeout, unavailable server, missing model, and parse failure states remain `submitted=0`, `order_allowed=False`, and `real_order=False`.
- Router, Execution, Order, and RiskGuard boundaries remain unchanged.

## 15. Curation Provenance Contract v1

- Curation requirements are task-specific. Candidate opportunity evidence is not
  a position or portfolio requirement.
- Correcting task ownership is a contract repair, not a quality-gate relaxation.
- Future outcome records carry `decision_task`, `decision_scope`, provider and
  teacher source, decision/payload schemas, payload quality, evidence summary,
  required/present/missing fields, and `training_eligibility_precheck`.
- The precheck is factual metadata only. The offline curation and feature gates
  remain authoritative for training eligibility.
- Historical source outcome JSONL is never rewritten. Records lacking persisted
  quality or feature provenance remain excluded with explicit reasons.
- LOCAL_ENGINE live flags remain false, Ollama remains developer-only, and no
  execution authority is granted by curation or training readiness.

## 16. Candidate Observation Contract v1

- Schema: `aits_local_engine_candidate_observation.v1`.
- A record is written only for an available prediction from a trained artifact
  using the actual provider decision payload.
- Observation records are always candidate-only and never modify the selected
  final provider, action, confidence, validation, Router, RiskGuard,
  LivePreflight, or Execution path.
- The observation joins model evidence with teacher/final provider metadata by
  `prediction_id`, `decision_id`, task, scope, timestamp, and
  `outcome_linkage_key`.
- Unavailable artifacts, insufficient factual features, validator rejection, or
  final-source conflict do not generate replacement wait/hold predictions.
- Provider flow continues when observation writing fails.
- LOCAL_ENGINE and Ollama live authority defaults remain disabled.
- The source candidate schema remains `aits_local_engine_decision_candidate.v1`; validator normalization is stored under `validator_metadata`.
- Writer contract `v2` exposes attempted/success state, status, blocker, and safe error type to future outcome records.
- Observation failure cannot be silently represented as an empty prediction ID.

## 17. Registry Latest Pointer Contract v1

- Every training run remains in registry history and the latest attempt status, including no-data and failed runs.
- The latest usable pointer accepts only trained entries backed by an existing `model.pkl`, feature columns, and encoding manifest.
- No-data or failed attempts never replace `latest_model.json` when a usable trained artifact exists.
- Predictor lookup resolves the latest usable model from the registry instead of trusting the latest attempt.
- Missing calibration may permit candidate-only observation metadata; it never grants final-action authority.
- Registry recovery reuses existing artifacts only. It never creates a trained flag, model artifact, prediction, or confidence value.
- Live decision and execution authority remain disabled.

## 18. Teacher Distillation Multi-Head Contract v1

- Teacher labels come only from an explicit external decision or an OpenAI/Gemini final decision joined by exact prediction/linkage identity.
- `local_safety_hold`, CostGuard cooldown, provider/network failure, and missing historical metadata never become external action labels.
- Training features are pre-decision `feature_context` values. Outcome, checkpoint, final-action, teacher-action, and post-provider comparison fields are excluded from the encoder.
- The multi-action head reports unsupported actions rather than fabricating samples. Current artifact support is determined from observed class counts.
- Confidence, risk, escalation, ETA, invalidation, and reason heads expose their evidence and insufficient-data state independently.
- Portfolio records never fall back to a position action head when exact-joined portfolio teacher labels are unavailable.
- Registry entries with `aits_local_engine_multi_head_model.v2` retain separate latest-usable and latest-attempt pointers; no-data attempts cannot replace the last usable artifact.
- Runtime output remains `candidate_only=true`, `applied_to_final_action=false`, `final_action_unchanged=true`, and all live authority flags false.
- See `app/docs/aits_local_engine_teacher_distillation_multi_head_v1.md` for dataset, model, evaluation, and remaining portfolio blocker details.
