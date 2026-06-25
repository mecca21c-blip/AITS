# AITS AI Output Contract v1

## Purpose

`aits.ai_output_contract.v1` is the canonical display contract for GPT, Gemini, and LOCAL calculation results. It is an observe/display contract only. It is not a Router action, execution plan, or order signal.

## Canonical Fields

- `schema`: `aits.ai_output_contract.v1`
- `symbol`, `requested_symbol`
- `provider_selected`, `provider_actual`
- `model`, `engine_label`
- `analysis_kind`: `provider_ai`, `local_calculation`, `provider_fallback`, or `insufficient_data`
- `source`
- `generated_at`
- `decision_code`, `decision_display`
- `briefing_summary`
- `basis_summary`
- `user_reason`
- `next_observation`
- `confidence`
- `is_valid`, `parse_status`, `fallback_used`, `warnings`
- `safety`

Safety is always display-only for this contract:

- `is_order_signal=False`
- `is_execution_plan=False`
- `order_allowed=False`
- `submitted=0`
- `real_order=False`
- `suggestion_only=True`
- `display_only=True`

## Decision Mapping

Raw provider actions are never shown directly in user-facing UI.

- `ENTER`, `BUY`, `LONG` -> `entry_review` -> `진입 검토`
- `SELL`, `EXIT`, `SHORT` -> `exit_review` -> `매도 검토`
- `HOLD`, `STAY` -> `hold` -> `보유 유지`
- `WAIT`, `WATCH`, `OBSERVE` -> `observe` -> `관망`
- `BLOCK`, `SKIP` -> `blocked` -> `판단 보류`
- empty, malformed, or unknown values -> `insufficient_data` -> `데이터 확인 필요`

The Korean display strings are review states, not order instructions.

## Text Sanitizer

The shared sanitizer removes or rewrites:

- Markdown code fences and HTML/script markup
- control characters and excessive whitespace
- foreign `KRW-*` symbols that do not match the requested/current symbol
- raw action tokens such as `ENTER`, `BUY`, `SELL`, `EXIT`, `STAY`, `WAIT`
- internal strings such as `unknown`, `USER`, `last_known_ai`, `local_calculation`, `preview_only`, and `submitted=0`
- imperative trade phrases into review-oriented language

Raw prompts, raw HTTP bodies, API keys, account payloads, and order payloads must not be stored in the contract.

## Provider Adapters

GPT/OpenAI and Gemini raw text are parsed into the same contract. Malformed JSON becomes a safe fallback contract.

LOCAL Basic calculation payloads become `analysis_kind=local_calculation` and `provider_actual=local`. LOCAL/Basic output must not be presented as a provider AI judgment.

Provider fallback separates selected and actual provider. For example, GPT selected with LOCAL fallback keeps:

- `provider_selected=gpt`
- `provider_actual=local`
- `fallback_used=True`

Fallback display metadata must include a sanitized reason code/display when the fallback is confirmed. Automatic LOCAL monitoring is not provider fallback: it remains `analysis_kind=local_calculation`, is displayed as automatic monitoring, and must not inherit GPT/Gemini selected-provider context without matching request-group proof.

## Provider Call Proof

External provider success requires runtime proof, not just a selected or configured engine.

For OpenAI/GPT and Gemini records, the contract may preserve compact proof metadata:

- `provider_call_attempted`
- `provider_request_sent_at`
- `provider_endpoint_type`
- `model_display_name`
- `model_requested`
- `model_returned`
- `http_status`
- `response_id`
- `provider_request_id`
- `usage_input_tokens`
- `usage_output_tokens`
- `usage_total_tokens`
- `elapsed_ms`
- `provider_success`
- `error_type`
- `error_code`

API keys, prompts, raw provider responses, account payloads, and order payloads are never stored in this proof metadata.

An external AI analysis success record requires `provider_call_attempted=True`, HTTP success, parse success, `provider_success=True`, and a response/request identifier. Legacy rows that only say GPT/Gemini without proof are displayed as unverified previous records rather than confirmed actual GPT/Gemini judgments.
- `engine_label=LOCAL 계산 기반`

## Stage Metadata Boundary

The contract remains the source of truth for decision content. Journal stage metadata only explains where that content appears in the operator workflow.

- `ai_original` is displayed as `AI 원판단`.
- `aits_shadow_final` is displayed as `AITS 모의판정`.
- A single decision group may contain at most one row per stage and symbol.
- Stage pairing uses `decision_group_id` plus symbol, not timestamp proximity.

Stage metadata may include `decision_group_id`, `record_stage`, `source_event`, `contract_hash`, `selected_engine`, `original_generation_engine`, `shadow_processing_method`, `model_invoked`, `invoked_model`, and `ollama_invoked`. These fields do not replace the output contract.

## Engine Provenance

Configured local model names and invoked model names are distinct. LOCAL Basic calculation displays as `LOCAL 계산 기반`. A local model such as `qwen2.5` may be displayed as `LOCAL ? qwen2.5` only when `ollama_invoked=True` and `invoked_model=qwen2.5` are recorded.

Manual LOCAL/Ollama diagnostic results are not active AI decisions. They must not publish `ai.reco.updated`, write `AISnapshotStore`, update detail-chart AI snapshots, or create `TradeLogShadowJournal` decision rows.

## Surface Wiring

The following surfaces should prefer contract fields:

- managed-tab central analysis
- detail-chart AI status, WHY, scenario, and next observation text
- recent AI judgment card
- Shadow/Preview Journal display and detail panel
- per-symbol AI snapshot cache

## Compatibility Policy

Existing consumers may temporarily read compatibility aliases such as `decision`, `decision_summary`, `reason`, and `next_action`. Those aliases are derived from `output_contract`; they are not a separate source of truth.

Snapshot and Shadow Journal rows may include `output_contract` while retaining legacy fields for restore compatibility. No DB migration is required for this contract.

## Trading Safety

This contract does not change trading strategy, Router action, Execution, Order, or RiskGuard behavior. All outputs remain `submitted=0`, `order_allowed=False`, and `real_order=False`.

## OpenAI Model Identity

`model_display_name`, `model_api_id`, `model_requested`, `model_returned`, and `invoked_model` are separate fields. For the GPT fast preset, the user-facing display name is `GPT-5.5 Instant`, while the current OpenAI API request alias is `chat-latest`. Legacy `gpt-5.5-instant` values are normalized before request dispatch and must not be sent as an API model id. A GPT success record still requires HTTP success, parse success, response/request proof, usage metadata when provided by the API, and `provider_success=True`.


## Provider Error Proof

Provider error proof fields include `error_type`, `error_code`, `error_param`, and `error_message`. Gemini adapters preserve Google `error.status` as the primary error code when available so UI, snapshot, and Journal displays can show a specific failure class instead of generic API failure. These fields are proof metadata only and do not change order safety; outputs remain `submitted=0`, `order_allowed=False`, and `real_order=False`.
