# AITS AI Output Contract v1

## Purpose

`aits.ai_output_contract.v1` is the canonical display contract for GPT, Gemini, and LOCAL calculation results.
It is an observe/display contract only. It is not a Router action, execution plan, or order signal.

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

LOCAL Basic calculation payloads become `analysis_kind=local_calculation` and `provider_actual=local`.
LOCAL/Basic output must not be presented as a provider AI judgment.

Provider fallback separates selected and actual provider. For example, GPT selected with LOCAL fallback keeps:

- `provider_selected=gpt`
- `provider_actual=local`
- `fallback_used=True`
- `engine_label=LOCAL 계산 기반`

## Compatibility Policy

Existing consumers may temporarily read compatibility aliases such as `decision`, `decision_summary`, `reason`, and `next_action`.
Those aliases are derived from `output_contract`; they are not a separate source of truth.

Snapshot and Shadow Journal rows may include `output_contract` while retaining legacy fields for restore compatibility.
No DB migration is required for this contract.

## Surface Wiring

The following surfaces should prefer contract fields:

- managed-tab central analysis
- detail-chart AI status, WHY, scenario, and next observation text
- recent AI judgment card
- Shadow/Preview Journal display and detail panel
- per-symbol AI snapshot cache

## Ollama Diagnostic Boundary

Manual LOCAL/Ollama diagnostic results are not active AI decisions.
They must not publish `ai.reco.updated`, write `AISnapshotStore`, update detail-chart AI snapshots, or create `TradeLogShadowJournal` decision rows.

## Trading Safety

This contract does not change trading strategy, Router action, Execution, Order, or RiskGuard behavior.
All outputs remain `submitted=0`, `order_allowed=False`, and `real_order=False`.
