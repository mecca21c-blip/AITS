# AITS Detail Chart Display Source Proof v1

## 1. Purpose

This proof document defines the runtime logs added for the AITS managed-symbol detail chart display source audit.

The proof scope is display provenance only. It does not change scoring formulas, data sources, provider connection logic, Router, RiskGuard, Execution, Order, database schema, or live-trading behavior.

Allowed source classifications:

- `real_market_data`
- `local_calculation`
- `row_session`
- `cache`
- `preview`
- `placeholder`
- `unknown`

## 2. Active Open Path

The active path for opening the detail chart is:

```text
tbl_ai_managed.cellDoubleClicked
-> MainWindow._on_ai_managed_table_double_clicked(row, col)
-> MainWindow._open_aits_large_chart_dialog_for_row(row)
-> AITSLargeChartDialog.set_summary(...)
-> MainWindow._render_aits_large_chart_dialog(symbol_text, dlg)
```

The active owner is `app/ui/app_gui.py`, using `tbl_ai_managed` and `ai_managed_rows`.

## 3. DetailChartProof Fields

Log prefix:

```text
[AITS][DetailChartProof]
```

Logged at detail chart open time in `_open_aits_large_chart_dialog_for_row`.

Fields:

| Field | Meaning |
|---|---|
| `symbol` | Resolved market symbol passed to the popup |
| `row` | Managed table row index |
| `owner` | `tbl_ai_managed` or fallback table owner |
| `source` | `ai_managed_rows` or `table_cell` |
| `has_price` | Whether the row/session has a current price display value |
| `has_change_rate` | Whether change rate display value exists |
| `has_target_price` | Whether target price display value exists |
| `has_ai_status` | Whether AI status display value exists |
| `has_score` | Whether a score display value exists |
| `confidence` | Parsed score confidence when numeric; otherwise `unknown` |
| `order_allowed` | Always `False` in this proof path |
| `submitted` | Always `0` in this proof path |

Example:

```text
[AITS][DetailChartProof] open symbol=KRW-BTC row=3 owner=tbl_ai_managed source=ai_managed_rows has_price=True has_change_rate=True has_target_price=True has_ai_status=True has_score=True confidence=0.720 order_allowed=False submitted=0
```

## 4. DisplaySourceProof Classification

Log prefix:

```text
[AITS][DisplaySourceProof]
```

Logged at detail chart render time in `_render_aits_large_chart_dialog`.

Fields:

| Field | Classification rule |
|---|---|
| `price` | `row_session` when row price level exists, otherwise `placeholder` |
| `candles` | `real_market_data` when Upbit candles are loaded, otherwise `placeholder` |
| `volume` | `real_market_data` when candles are loaded, otherwise `placeholder` |
| `indicators` | `local_calculation` when dataframe exists, otherwise `placeholder` |
| `score` | `row_session` when score label has text, otherwise `placeholder` |
| `ai_status` | `row_session` when row status exists, otherwise `placeholder` |
| `ai_reason` | `preview` when AI Output Contract exists, `row_session` when reason label has text, otherwise `placeholder` |
| `selected_engine` | `preview` when session Preview provider owns UI, otherwise `cache` |
| `actual_engine` | `preview` when last response provider exists, otherwise `unknown` |
| `preview_state` | `preview` when session/AI preview exists, otherwise `unknown` |

Example:

```text
[AITS][DisplaySourceProof] symbol=KRW-BTC price=row_session candles=real_market_data volume=real_market_data indicators=local_calculation score=row_session ai_status=row_session ai_reason=preview selected_engine=preview actual_engine=preview preview_state=preview
```

## 5. ScoreProof Result

Log prefix:

```text
[AITS][ScoreProof]
```

Logged at detail chart open time after the display score is resolved.

Fields:

| Field | Meaning |
|---|---|
| `symbol` | Resolved market symbol |
| `owner` | Best-known display/calculation owner: `_calc_basic_ai_score`, `_get_ai_confidence`, `table_score_column`, or `unknown` |
| `display_score` | Numeric display score when parseable, otherwise `unknown` |
| `confidence` | `display_score / 100` when parseable, otherwise `unknown` |
| `source` | `row_session` for active managed rows, otherwise `unknown` |
| `placeholder` | `True` when display score is not parseable |
| `user_added` | Whether row source/source_type indicates a user-added symbol |
| `managed_pool_row` | Whether the source row is from `ai_managed_rows` |

Example:

```text
[AITS][ScoreProof] symbol=KRW-BTC owner=_calc_basic_ai_score display_score=72.0 confidence=0.720 source=row_session placeholder=False user_added=True managed_pool_row=True
```

The detail popup remains a display owner, not a scoring formula owner.

## 6. EnginePathProof Result

Log prefix:

```text
[AITS][EnginePathProof]
```

Logged in two places:

1. At detail chart open time, before popup rendering.
2. Immediately before an existing OpenAI preview call inside `_build_gpt_preview_output`.

Fields:

| Field | Meaning |
|---|---|
| `selected` | `_get_aits_engine_ssot()` result where available |
| `saved` | saved provider from `strategy.ai_provider` or normalized OpenAI provider in the GPT preview path |
| `actual` | `_get_aits_last_response_provider()` where available |
| `source` | `preview` or `strategy.ai_provider` |
| `api_call_allowed` | Whether this exact existing path is about to call provider preview |
| `api_call_attempted` | Whether a provider API call is being attempted in that existing path |
| `order_allowed` | Always `False` |
| `submitted` | Always `0` |

Open-time example:

```text
[AITS][EnginePathProof] selected=gpt saved=openai actual=unknown source=strategy.ai_provider api_call_allowed=False api_call_attempted=False order_allowed=False submitted=0
```

Existing OpenAI preview attempt example:

```text
[AITS][EnginePathProof] selected=gpt saved=openai actual=unknown source=strategy.ai_provider api_call_allowed=True api_call_attempted=True order_allowed=False submitted=0
```

No API key, request header, prompt body, model payload, or secret body is logged.

## 7. Real Data / Placeholder / Unknown Table

| Display item | Expected proof source |
|---|---|
| Market symbol | `row_session` through `DetailChartProof source=ai_managed_rows` |
| Current price label | `row_session` unless missing |
| Candles | `real_market_data` only when the candle list is non-empty |
| Volume | `real_market_data` only when candles exist |
| Indicators | `local_calculation` only when candle dataframe exists |
| Score | `row_session` when score label is parseable; otherwise `placeholder` |
| AI status | `row_session` when row status exists; otherwise `placeholder` |
| AI reason | `preview`, `row_session`, or `placeholder` |
| Selected engine | `preview` or `cache` source classification; exact engine value is in `EnginePathProof` |
| Actual engine | `preview` when last response provider exists; otherwise `unknown` |
| Order state | `order_allowed=False`, `submitted=0` |

## 8. API Call Boundary

The proof logs do not add provider API calls.

The detail popup already has an OpenAI preview path in `_build_gpt_preview_output`. This patch only logs `EnginePathProof` immediately before that existing call if the existing guards allow it.

Rules:

- GPT/GEMINI connection logic is not changed.
- API key bodies are not logged.
- Full model payloads/prompts are not logged.
- If no existing provider call is reached, `api_call_attempted=False` remains the open-time proof state.
- Gemini equivalent behavior remains unproven in this detail popup path.

## 9. Safety Boundary

Confirmed intended boundary:

- No Router call added.
- No RiskGuard call added.
- No Execution call added.
- No Order call added.
- No buy/sell/cancel/liquidation path added.
- No score formula change.
- No market data source replacement.
- No database migration.
- `submitted=0` is explicitly logged by the proof path.

## 10. Next Fix Candidates

1. `FUNCTION-FIX-01 Detail Chart Input Contract`
   - Replace string/row assembly with a read-only detail-chart input contract carrying source and placeholder metadata.

2. `FUNCTION-FIX-02 Detail Score Source Badge`
   - Show whether the displayed score came from Basic calculation, market candidate scoring, row payload, AI Output Contract, or placeholder.

3. `FUNCTION-FIX-03 Detail Provider Preview Guard`
   - Decide whether the detail popup should perform live provider preview calls or only display last-known preview state.

4. `FUNCTION-FIX-04 Gemini Detail Preview Parity`
   - If provider preview is allowed in the detail popup, route GPT/GEMINI through one owner and proof log both providers consistently.

## ChatGPT Verification Summary

- `DetailChartProof` proves which row and managed source opened the chart.
- `DisplaySourceProof` classifies price, candles, volume, indicators, score, AI status, AI reason, and engine display sources.
- `ScoreProof` proves that the popup displays upstream row/session score and does not own the score formula.
- `EnginePathProof` proves selected/saved/actual engine source and whether an existing OpenAI preview call was attempted.
- The proof path logs `order_allowed=False` and `submitted=0`.
