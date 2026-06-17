# AITS Managed Detail Data Integrity Audit v1

## 1. Purpose

This audit records the active data path used when a user opens the managed-symbol detail chart from the AITS symbol-management tab.

The goal is to distinguish real market data, local calculation, UI/session state, AI/provider preview state, and placeholders before deeper functional integration begins. This document does not authorize Router, Execution, Order, RiskGuard, provider connection, database migration, or live-trading changes.

## 2. Double Click Active Path

The active AITS symbol-management tab is still a mixed owner:

| Layer | Owner |
|---|---|
| Bottom navigation tab | `WatchlistTab` plus app_gui managed-pool insertions |
| Active managed table | `MainWindow.tbl_ai_managed` in `app/ui/app_gui.py` |
| Legacy watchlist table | `WatchlistTab` in `app/ui/tabs/watchlist_tab.py`; still present, but not the main detail-chart owner |
| Detail chart popup | `AITSLargeChartDialog` in `app/ui/app_gui.py` |

Active double-click signal:

```text
tbl_ai_managed.cellDoubleClicked
-> MainWindow._on_ai_managed_table_double_clicked(row, col)
-> MainWindow._open_aits_large_chart_dialog_for_row(row)
-> AITSLargeChartDialog.set_summary(...)
-> MainWindow._render_aits_large_chart_dialog(symbol_text, dlg)
```

The lock column is handled separately by `_on_ai_managed_cell_double_clicked`. Other managed-table double clicks open the large detail chart.

## 3. Detail Chart Input Payload

`_open_aits_large_chart_dialog_for_row(row)` builds the popup input from the selected table row and `self.ai_managed_rows`.

Primary payload fields:

| Field | Source |
|---|---|
| `row` | `tbl_ai_managed` selected/double-clicked row index |
| `symbol_text` | `ai_managed_rows[row]["symbol"]`, then `market`, then `code`; fallback to table item `UserRole`, detail label text, or coin name |
| `display_name` | `_format_aits_coin_display_name(symbol_text)`, row `name`, or symbol fallback |
| current price | row `price` |
| change rate | row `change_rate` or `change_pct` |
| target price | row `target_price` |
| source/category | row `source` |
| AI/user status | `_managed_status_build04(row)` and row `ai_status` |
| score text | `_get_ai_confidence(row)` result |
| reason text | `_extract_current_aits_ai_reason_text()` |
| action badge | `_get_aits_popup_action_badge(row)` |
| decision banner | `_get_aits_popup_decision_banner(row)` |

The detail popup does not receive a clean typed DTO yet. It receives a row index, pulls from `ai_managed_rows`, formats several strings, and then the dialog parses those strings back into labels.

## 4. Data Source Map

| Displayed value | Current source | Classification |
|---|---|---|
| Symbol / market code | `ai_managed_rows[row]["symbol"]`, `market`, `code`, or table `UserRole` fallback | Real row/session data when present; fallback can be UI-derived |
| Current price | `ai_managed_rows[row]["price"]`; chart overlays also use `_get_aits_popup_price_levels(row)` | Real/cached market row value when row was refreshed; placeholder/empty if row lacks price |
| Candles | `_render_aits_large_chart_dialog` -> `_fetch_aits_large_chart_candles` -> `_fetch_upbit_candles` -> Upbit candle HTTP GET | Real read-only market API data when request succeeds |
| Volume | Candle payload fields rendered through mplfinance dataframe/panels | Real read-only market API data when candles exist |
| RSI / MACD / MA / Bollinger | Local indicator builders such as `_aits_build_mpf_rsi_panel_addplots`, MA/MACD/Bollinger calculations from candle dataframe | Local calculated values |
| Target / stop levels | row `target_price`, `stop_loss`; `_update_ai_pool_statuses` can derive them from Basic settings and price | Local policy/calculation value, not an order |
| AI status | row `ai_status`, `_managed_status_build04`, popup badge/banner helpers | Local/session state; not proof of provider judgement by itself |
| Score | `_get_ai_confidence(row)` display value; upstream score can come from `_calc_basic_ai_score`, `_score_market_candidate`, or external score payloads | Mixed: calculated or upstream payload; detail popup itself is not the score owner |
| Reason / next action text | current detail reason widgets, popup badge/banner, narrative builders, or AI Output Contract if available | Mixed: local narrative, prior shadow/preview record, or provider preview |
| Selected engine | `_get_aits_engine_ssot()` | Session Preview first, then saved `strategy.ai_provider`; normalized to `gpt`, `gemini`, or `basic` |
| Actual engine | `_get_aits_last_response_provider()` and `ai_reco.get_last_decision()` metadata | Last known runtime/response metadata only; may be empty |
| Preview / order state | UI copy and safety flags in preview contracts | Preview-only display; no submitted order observed in this path |

## 5. Score Calculation Owner

There are multiple score-related paths and they must not be treated as one owner.

### Active managed-pool path

`app/ui/app_gui.py` owns the active managed detail display.

Relevant functions:

| Function | Role |
|---|---|
| `_calc_basic_ai_score(row)` | Basic/local rule-based score from row change rate, market-wide rows, Basic settings, volume threshold, cooldown, risk filters, and selection/risk mode |
| `_update_ai_pool_statuses()` | Applies Basic settings to managed rows, derives target/stop levels, and updates status candidates |
| `_score_market_candidate(row_obj)` | Market shortlist score from trade value, change rate, and price bias |
| `_get_ai_confidence(row)` | Converts row/upstream score into the confidence text used by the detail popup |
| `_open_aits_large_chart_dialog_for_row(row)` | Displays score text; it does not own the scoring formula |

`_calc_basic_ai_score(row)` returns a dict containing `score`, `reasons`, `trend_score`, `volume_score`, and `risk_penalty`. It is local calculation, not provider judgement.

`_score_market_candidate(row_obj)` returns a float candidate score from market trade value/change/price fields. It is a shortlist/ranking helper, not an order signal.

### Legacy WatchlistTab path

`app/ui/tabs/watchlist_tab.py` owns a separate legacy watchlist score display path:

```text
handle_ai_reco(payload)
-> normalize scores from payload["scores"] or payload items score/score_norm/score_total
-> self._ai_scores
-> _fill_score_column(symbols)
```

`WatchlistTab.update_ai_scores(wl_symbols, scores)` also updates `_ai_scores` and redraws the score column. This path is a display model for the legacy watchlist table and should not be assumed to be the active managed detail score owner.

## 6. Engine Setting Reflection Path

Engine selection is read through `_get_aits_engine_ssot()` in `app/ui/app_gui.py`.

Priority:

1. Active session Preview provider when `_applied_ai_is_preview` and `_applied_ai_provider` are set.
2. Saved `strategy.ai_provider` from settings.
3. Normalization:
   - `local`, `basic`, `basic ai`, `basic_ai` -> `basic`
   - `gemini`, `google`, `google gemini` -> `gemini`
   - otherwise -> `gpt`

Actual response provider is read by `_get_aits_last_response_provider()`, which checks `_last_response_provider` and `app.services.ai_reco.get_last_decision()` metadata such as `actual_engine`, `provider`, `source`, `engine_mode`, and `selected_engine`.

Important audit finding:

The detail popup contains `_build_gpt_input_contract()` and `_build_gpt_preview_output()`. `_build_gpt_preview_output()` is preview-only and explicitly avoids order execution, but when saved strategy provider is OpenAI/GPT and an OpenAI key is present, it can call `OpenAI(...).responses.create(...)` to produce a GPT Preview contract.

Current provider behavior by selection:

| Selected provider | Detail popup behavior observed from code |
|---|---|
| LOCAL / BASIC | Uses local/basic row state, calculated score, and Basic Preview copy. No external AI provider call is required for the Basic path. |
| GPT / OpenAI | May call OpenAI preview from `_build_gpt_preview_output()` if saved provider/key/model allow it. This is provider API activity, but still preview-only and not a Router/Order path. |
| GEMINI | `_get_aits_engine_ssot()` can report `gemini`, but the detail popup's named preview builder is GPT/OpenAI-specific. No equivalent Gemini preview call was confirmed in the detail popup path during this audit. |

This means the displayed engine state and the detail-popup preview path are not fully symmetrical across LOCAL/GPT/GEMINI yet.

## 7. Placeholder / Real Data Classification

| Area | Real value when | Placeholder / uncertain when |
|---|---|---|
| Symbol | `ai_managed_rows` has `symbol`/`market`/`code` | Fallback uses table text or current detail label |
| Candles | Upbit candle request succeeds | `_fetch_upbit_candles` returns `[]`; chart renders no-data text |
| Indicators | Candle dataframe is valid | Candle dataframe missing/empty |
| Current price | Managed row refresh populated `price` | Row has no price or stale row |
| Score | Upstream Basic/market score or score payload exists | Score text is empty/derived from UI label; detail popup does not prove calculation |
| AI status | Managed row status exists | Status falls back to Watching/display formatting |
| Reason/action | Current detail reason, badge, banner, shadow record, or AI Output Contract exists | Local narrative/placeholder copy is used |
| Selected engine | `_get_aits_engine_ssot()` returns normalized provider | It only proves selected/saved/Preview state, not actual model response |
| Actual engine | Last response metadata exists | Empty or stale last response provider |
| Order execution | Not present in this path | Any future order/log integration must be separate and explicit |

## 8. Safety Boundary

Confirmed safety boundary for this audit:

- No Router call was added.
- No Execution call was added.
- No Order call was added.
- No RiskGuard live application was added.
- No provider connection logic was modified.
- No DB migration or cleanup was performed.
- No actual buy, sell, cancel, liquidation, or submitted order path is part of this audit.
- The detail chart may read Upbit candle data for display.
- The detail popup may perform OpenAI preview generation under the GPT/OpenAI provider path, but this is not a live order path and should be reviewed in a later integration Goal.

## 9. Findings

1. The AITS symbol-management tab still has mixed ownership: `WatchlistTab` is the tab class, while `app_gui.py` owns the active managed table and detail popup path.
2. The active double-click path is `tbl_ai_managed.cellDoubleClicked -> _on_ai_managed_table_double_clicked -> _open_aits_large_chart_dialog_for_row`.
3. The detail chart input payload is row/string based, not a typed contract. This increases the chance that real values and placeholders are displayed without clear provenance.
4. Candle, volume, and chart indicator data are real/read-only market data plus local calculations when Upbit candle requests succeed.
5. The detail popup does not own score calculation. It displays score text from upstream managed row helpers and labels.
6. Basic/local score ownership is in `_calc_basic_ai_score` and `_score_market_candidate` for active managed rows; legacy `WatchlistTab` score ownership is `_ai_scores` from recommendation payloads.
7. Selected engine display comes from `_get_aits_engine_ssot`; actual engine comes from last response metadata. These are distinct layers and can diverge.
8. GPT/OpenAI detail preview can make an OpenAI preview API call from inside the popup path. Gemini does not appear to have an equivalent detail-preview builder in the inspected path.
9. No evidence was found that opening the detail chart calls Router, Execution, Order, or RiskGuard.
10. No proof log was added in this Goal because static code inspection was enough to map the active path. Runtime proof can be added later if needed.

## 10. Next Recommended Fix Goals

1. `FUNCTION-AUDIT-02 Detail Chart Runtime Proof Logs`
   - Add read-only `[AITS][DetailChartProof]`, `[AITS][ScoreProof]`, and `[AITS][EnginePathProof]` logs at popup open, candle load, score display, and engine display points.

2. `FUNCTION-FIX-01 Detail Chart Input Contract`
   - Replace ad hoc row/string payload assembly with a read-only `DetailChartInputPayload` builder that records source and placeholder status for every field.

3. `FUNCTION-FIX-02 Detail Score Source Badge`
   - Display whether the score is Basic calculated, market candidate score, AI Output Contract score, legacy payload score, or placeholder.

4. `FUNCTION-FIX-03 Detail Engine Path Guard`
   - Make selected engine, actual engine, and preview provider explicit in the detail popup.
   - Prevent GPT-only preview wording from appearing as a Gemini/LOCAL judgement.

5. `FUNCTION-FIX-04 Detail Provider Preview Ownership`
   - Decide whether detail popup provider previews are allowed.
   - If allowed, route GPT/GEMINI through a single preview provider owner with proof logs.
   - If not allowed, keep detail popup fully read-only and use last known AI Output Contract only.

## ChatGPT Verification Summary

- Double Click path: `tbl_ai_managed.cellDoubleClicked -> _on_ai_managed_table_double_clicked -> _open_aits_large_chart_dialog_for_row -> AITSLargeChartDialog`.
- Score owner: active managed scores are owned upstream by app_gui Basic/market scoring helpers or row payloads; the detail popup only displays them.
- Engine path: selected engine is `_get_aits_engine_ssot`; actual engine is last-response metadata.
- Placeholder risk: detail popup mixes row data, UI label text, local calculations, and provider preview output without a typed source contract.
- submitted: this audit found no detail-chart path that submits orders or calls Router/Execution/Order/RiskGuard.
