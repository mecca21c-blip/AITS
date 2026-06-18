# AITS Detail Chart Display Contract v1

## 1. Purpose

This document defines the display contract for the AITS detail chart.

The detail chart must make it clear whether ETA, WHY, briefing, evidence, next action, and trade-plan copy came from market data, Basic/local calculation, last-known AI analysis, or a placeholder.

This is a display contract, not an execution contract. It does not authorize orders, Router bypass, Risk Guard bypass, or Provider/API calls.

## 2. Detail Chart Role

The detail chart is a read-only explanation surface for the selected managed symbol.

It may show:

- Real market chart data.
- Local indicators and AITS Score v2.
- Basic/local calculation summary.
- Last-known AI analysis when it already exists.
- Placeholder text when AI analysis has not been explicitly generated.

Opening the detail chart is not an AI call trigger.

## 3. Contract Schema

Schema name:

```text
detail_chart_display_contract.v1
```

Required fields:

```text
symbol
display_mode
data_source
interest_reason
current_state_reason
eta
why_summary
observation_points
next_action
trade_plan_summary
ai_output_state
generated_engine
generated_at
safety_flags
```

## 4. Source Types

Allowed source values:

- `real_market_data`: chart candles, price, volume, or market rows.
- `local_calculation`: Basic/local calculation, technical indicators, scenario heuristics, or AITS Score v2.
- `row_session`: selected managed row/session state.
- `last_known_ai`: already-generated AI analysis from a previous explicit AI request.
- `ai_preview`: explicit AI preview output when a future explicit preview button creates it.
- `placeholder`: no usable source exists.
- `unknown`: source could not be classified.

## 5. Display Modes

Allowed display modes:

- `basic_summary`: Basic/local calculation summary. This is the default mode.
- `last_known_ai`: previously generated AI analysis exists and is being displayed.
- `ai_analysis`: explicit AI analysis exists for the selected symbol.
- `calculation_preview`: local calculation preview used for observation only.
- `placeholder`: no analysis or calculation explanation is available.

The current selected engine must not be used by itself to classify content as AI analysis. A generated AI payload or equivalent metadata must exist.

## 6. ETA Meaning

ETA is not the next evaluation time.

When no AI Output Contract exists, ETA is a Basic/local calculation reference window for the current observation scenario.

When an AI Output Contract exists, ETA may be displayed as an AI observation ETA tied to the generated analysis.

Required ETA fields:

```text
label
source
seconds
explanation
is_ai_forecast
state_type
```

Rules:

- `source=local_calculation`: calculation observation window only.
- `source=last_known_ai` or `source=ai_preview`: AI observation ETA.
- `source=placeholder`: no ETA should be treated as meaningful.
- `is_ai_forecast` must be false unless generated AI output exists.

## 7. WHY Structure

WHY is split into three layers:

- `interest_reason`: why the symbol is in Managed Candidates or the scanner-derived pool.
- `current_state_reason`: why the current state is watch, wait, hold, risk, or manual hold.
- `why_summary`: short user-facing summary.

Basic/local mode may use AITS Score v2 reasons, trade value, momentum, volatility, status, and managed row state.

AI mode may use last-known AI reasons when available. If AI reasons are missing, the display must fall back to local calculation and label the source accordingly.

## 8. Next Action And Trade Plan

`next_action` and `trade_plan_summary` are display guidance only unless a separate execution contract exists.

Required safety flags:

```text
is_order_signal=false
is_execution_plan=false
```

If Router/Execution has not produced an execution contract, the text must be classified as:

- observation scenario
- observation condition
- not an order signal
- not an execution plan

Examples:

- Watch whether trade value remains strong.
- Watch price recovery or trend confirmation.
- Use explicit AI analysis refresh for deeper interpretation.

## 9. AI Output Missing

If no explicit AI output exists:

- `display_mode=basic_summary` or `calculation_preview`.
- `ai_output_state=missing` or `placeholder`.
- `generated_engine=BASIC` or `LOCAL`.
- ETA must not look like an AI forecast.
- Trade plan must not look like an execution plan.

## 10. AI Output Available

If last-known AI analysis exists:

- `display_mode=last_known_ai` or `ai_analysis`.
- `data_source=last_known_ai`.
- Generated engine metadata must be preserved.
- Existing analysis must not be rewritten when the user changes the current engine.

Engine badge policy:

- GPT: `G`
- Gemini: `g`
- LOCAL: `L`
- Basic/local fallback: `BASIC` or `L`

## 11. Safety Rules

The contract must always carry:

```text
api_call_allowed=false
api_call_attempted=false
order_allowed=false
submitted=0
```

Forbidden:

- Trigger GPT/Gemini/OpenAI from detail chart open.
- Reintroduce automatic GPT Preview on detail chart open.
- Treat Basic/local ETA as AI forecast.
- Treat observation copy as an order or execution plan.
- Bypass Router, Risk Guard, Order, or Execution.
- Log secrets, account payloads, API keys, or full Provider payloads.

## 12. Implementation Note

`DETAIL-CHART-CONTRACT-01` introduces an internal display contract helper in `app/ui/app_gui.py`.

The helper stores a compact contract payload and emits a short `[AITS][DetailChartContract]` log with schema, symbol, display mode, source, ETA source, WHY source, AI output state, and safety flags.

The existing UI is not redesigned in this Goal. ETA/WHY copy cleanup and a future explicit detail chart AI Preview button are separate Goals.

## 13. Follow-up Goals

Recommended follow-up Goals:

- `DETAIL-CHART-ETA-WHY-01`: apply contract-driven ETA, WHY, and observation-condition copy.
- `DETAIL-CHART-BASIC-SUMMARY-01`: separate Basic/local detail summary cards from AI analysis cards.
- `DETAIL-CHART-AI-PREVIEW-BUTTON-01`: add an explicit detail-chart AI Preview refresh button.
- `DETAIL-CHART-PLACEHOLDER-CLEANUP-01`: remove confusing placeholders and AI-looking labels without source.

## 14. DETAIL-CHART-ETA-WHY-01 Implementation Note

`DETAIL-CHART-ETA-WHY-01` applies the display contract to detail-chart wording for ETA, WHY, observation points, next action, and trade-plan copy.

Implemented display rules:

- `basic_summary` mode must use calculation-based wording, not AI judgement wording.
- Basic/local mode labels the intent area as `계산 기반 관찰 요약`.
- Basic/local ETA is labeled `계산 기반 관찰 구간`.
- Basic/local scenario copy is labeled `관찰 시나리오` and `계산 기반 참고`.
- AI output modes may use `AI 관찰 시나리오`, `AI 관찰 ETA`, and `AI 다음 관찰 조건`.
- ETA copy must state that it is not the next evaluation time.
- WHY copy is split into:
  - why the symbol is managed,
  - why the current state is being shown,
  - what the system is waiting for.
- `next_action.is_order_signal=false` must be visible as observation-only copy.
- `trade_plan_summary.is_execution_plan=false` must be visible as not an execution plan.
- Raw internal reason keys must be translated or replaced with safe fallback text.

Safety remains unchanged:

- Detail chart open is not an AI call trigger.
- No GPT/Gemini/OpenAI call is added.
- No detail-chart AI Preview button is added in this Goal.
- No Router, Risk Guard, Order, or Execution path is changed.
- `submitted=0` remains the expected state.

## 15. DETAIL-CHART-SOURCE-CONSISTENCY-01 Implementation Note

`DETAIL-CHART-SOURCE-CONSISTENCY-01` separates AI analysis state from execution-contract state in the detail chart.

Display rules:

- If recent AI analysis exists, the UI says `최근 AI 분석 참고`.
- If no recent AI analysis exists, the UI says `최근 AI 분석 없음` and `계산 기반 요약`.
- Missing Router/Execution contract is shown as execution status, not as AI-analysis absence.
- Execution status copy uses `주문 실행 계약 없음`, `Router/Execution 미적용`, or `실거래 주문과 연결되지 않음`.
- `USER` and `user_added` are displayed as user-friendly source text such as `사용자가 관리종목으로 등록한 종목입니다`.
- Internal strings such as `local_calculation`, `row_session`, `placeholder`, `detail_chart_open_guard`, `is_order_signal`, and `is_execution_plan` must not be shown directly on the user surface.
- WHY remains a three-layer structure:
  - why the symbol is managed,
  - why the current state is shown,
  - what the display is waiting for.
- ETA copy must not use standalone `유지 예상` as if it were an AI trade plan.
- `submitted=0`, `order_allowed=False`, and non-execution semantics remain unchanged.

This Goal does not add AI Preview buttons, Provider/API calls, background AI calls, Router changes, or Execution changes.

## 16. DETAIL-CHART-MODE-UNIFICATION-01 Implementation Note

`DETAIL-CHART-MODE-UNIFICATION-01` makes `display_mode` the single source of truth for the detail-chart user surface.

Display rules:

- The detail chart must not show `recent AI analysis missing` and `recent AI analysis reference` in the same screen.
- AI status, AI operation center, ETA, WHY, observation scenario, next action, and execution notice all share the same mode labels.
- `basic_summary` uses:
  - `최근 AI 분석 없음 · 계산 기반 요약`
  - `계산 기반 관찰 요약`
  - `계산 기반 관찰 구간`
  - `관찰 시나리오`
- `last_known_ai` or `ai_analysis` uses:
  - `최근 AI 분석 참고`
  - `AI 관찰 시나리오`
  - `AI 관찰 ETA`
  - `AI 판단 참고 · 주문 실행 아님`
- A last-known AI payload is shown as AI analysis only when it belongs to the selected symbol and has generation metadata plus actual analysis content.
- If the selected-symbol match or generation metadata is unclear, the display falls back to `basic_summary`.
- ETA/WHY/operation labels are corrected from the mode label bundle before display, rather than being recalculated by separate UI writers.
- Mode guard logs may record safe corrections, but they must not dump full payloads.

Safety remains unchanged:

- Detail chart open is not an AI call trigger.
- No GPT/Gemini/OpenAI call is added.
- No detail-chart AI Preview button is added in this Goal.
- No Router, Risk Guard, Order, or Execution path is changed.
- `submitted=0` remains the expected state.
