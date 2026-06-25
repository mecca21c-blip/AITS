# AITS AI Call Policy v1

## 1. Purpose

This document defines when AITS may call GPT, Gemini, or LOCAL AI engines.

The purpose is to reduce token waste while preserving the ability to catch important opportunity and risk events. This is a policy baseline, not an implementation document. Code changes, UI changes, Router changes, Execution changes, and Provider/API wiring changes must be handled by later Goals.

## 2. Engine Roles

### Basic Engine

Basic Engine is not AI. It is the always-on calculation and fact-provider layer.

Basic Engine owns:

- Market data collection and normalization.
- Current price, trade value, volume, and liquidity preparation.
- AITS score calculation.
- Candidate compression and ranking.
- Rank-change detection.
- Score-change detection.
- Risk-candidate detection.
- AI call candidate selection.

### GPT and Gemini

GPT and Gemini are paid AI judgement engines.

They may be used for:

- Interpretation of important candidate or risk events.
- Briefing, reasoning, next-action, and scenario generation.
- Buy, hold, wait, risk, or rotation judgement support.

They must not place orders directly. Their output is advisory and must not bypass Decision Router, Risk Guard, or Execution boundaries.

### LOCAL

LOCAL is the local/internal judgement engine.

LOCAL may use Basic calculation results for low-cost judgement or briefing. It may be used more frequently than GPT/Gemini, but it must still follow explicit UI and operation policy paths. LOCAL output is also advisory and must not directly place orders.

## 3. Core Principles

- UI refresh is not an operation judgement trigger.
- AI analysis refresh is an explicit AI judgement request.
- Opening a detail chart is not an automatic AI call trigger.
- Basic score is a candidate-compression filter for AI calls.
- v1 does not use absolute score thresholds to trigger AI calls.
- Score thresholds must be calibrated later with accumulated operating data.
- GPT/Gemini calls must have cooldowns and call limits.
- AI judgement does not directly become an order.
- AI judgement must still pass Decision Router, Risk Guard, and Execution conditions before any future execution path.

## 4. Absolute Score Threshold Deferred

The policy "call AI when AITS score is 70 or higher" is not used in v1.

Reasons:

- Basic Score v2 is a new scoring formula.
- There is not enough score-by-outcome performance data yet.
- Absolute thresholds can cause both over-calling and under-calling.

Instead, v1 selects AI call candidates using:

- Score change.
- Rank change.
- Trade value change.
- Holding risk events.
- Explicit user request.

## 5. Event-Based AI Call Candidates

### Buy-Candidate Events

GPT/Gemini calls may be considered when Basic Engine detects one or more of:

- New entry into Top N candidates.
- Sharp score increase versus the previous scan.
- Sharp rank increase.
- Trade value surge.
- Volume surge.
- Theme or market attention surge.
- Condition improvement after a sustained wait period.

### Holding Risk Events

GPT/Gemini calls may be considered when Basic Engine detects one or more of:

- Sharp AITS score drop for a holding.
- Loss rate approaching a warning range.
- Price approaching stop-loss range.
- Sudden drawdown.
- Volatility expansion.
- Pullback risk after take-profit range.
- Need for hold, reduce, or rotation judgement.

### Explicit User Events

AI calls are allowed when the user explicitly requests them through:

- AI analysis refresh.
- Detail-chart AI Preview refresh.
- Manual AI judgement request for a specific symbol.

## 6. Cooldown Policy Draft

Initial recommended cooldowns:

- Same-symbol buy-candidate AI judgement: 10 to 15 minutes.
- Same-holding risk judgement: 3 to 5 minutes.
- Global GPT/Gemini minimum interval: 1 to 2 minutes.
- Maximum GPT/Gemini symbols per cycle: 1 to 3.
- Manual AI analysis button cooldown: 30 to 60 seconds.

These values are v1 policy drafts. Exact numbers must be tuned later with operating data.

## 7. Status Refresh Policy

Status refresh is a cost-free data and screen refresh.

Status refresh must not trigger GPT/Gemini calls. It is not an order judgement trigger.

Allowed work during status refresh:

- Current price refresh.
- AITS score refresh.
- Scanner list refresh.
- Managed Candidates refresh.
- Holdings, trade log, and investment center screen refresh.

## 8. AI Analysis Refresh Policy

AI analysis refresh is an explicit user request for AI judgement.

Behavior:

- If the selected engine is GPT, a GPT call may be made.
- If the selected engine is Gemini, a Gemini call may be made.
- If the selected engine is LOCAL, a LOCAL judgement may be made.
- Results are displayed as briefing, reasons, next actions, or scenarios.
- Results must include the generation engine badge.
- Results must not directly trigger orders.

## 9. Detail Chart Open Policy

Opening a detail chart is not an automatic AI call trigger.

The detail chart displays last-known AI analysis. If no last-known analysis exists, it displays "AI analysis unavailable" or an equivalent placeholder.

New AI analysis from the detail chart is allowed only through an explicit button inside the chart or a separate AI analysis refresh action. If an AI analysis is generated from the detail chart, the chart must show the engine that generated it.

## 10. AI Engine Badge Policy

AI judgement, briefing, reasons, and next actions must record the engine that generated them.

The badge represents the generation-time engine, not the currently selected engine. If the user changes engines later, existing briefing output keeps its original generation badge.

Badge labels:

- GPT: `G`
- Gemini: `g`
- LOCAL: `L`

Badge colors should follow the signature colors of the existing engine selection UI.

## 11. Operation Loop Policy

The operation loop is separate from UI refresh.

The operation loop continuously monitors through Basic Engine. Basic Engine creates AI call candidate events. GPT/Gemini calls may happen only when candidate events pass cooldown and per-cycle call limits.

AI judgement results must pass Decision Router, Risk Guard, and Execution conditions before any future order path. v1 does not change live-trading or execution behavior.

## 12. Prohibited Policy

The following are prohibited:

- AI directly placing orders.
- Buying or selling based only on GPT/Gemini judgement.
- Calling GPT/Gemini from status refresh.
- Automatically calling GPT/Gemini when opening a detail chart.
- Calling AI based only on an absolute AITS score value.
- Bypassing Router, Risk Guard, or Execution.
- Changing the `submitted=0` principle without a separate explicit live-execution Goal.

## 13. Next Goal Candidates

- `AI-CALL-POLICY-02` separate status refresh from AI calls.
- `DETAIL-CHART-AI-PREVIEW-GUARD-01` block automatic GPT calls on detail chart open.
- `AI-ANALYSIS-REFRESH-BUTTON-01` add explicit AI analysis refresh button.
- `AI-CALL-COOLDOWN-01` add provider and symbol cooldown skeleton.
- `AI-EVENT-CANDIDATE-01` define Basic event candidate generation.
- `AI-BRIEFING-BADGE-01` display generation engine badge.

## 14. AI-CALL-POLICY-02 Implementation Note

`AI-CALL-POLICY-02` separates status refresh from explicit AI analysis refresh.

Implemented policy intent:

- Status refresh is data and screen refresh only.
- Status refresh must not schedule GPT/Gemini recommendation reinforcement.
- The explicit `AI 분석 새로고침` button owns manual AI analysis refresh.
- The manual AI analysis button may use the currently selected engine.
- GPT/Gemini may create paid API calls only from explicit analysis refresh or later event-policy paths.
- LOCAL/Basic analysis remains available without paid Provider/API calls.
- The manual AI analysis button has a 30 second click cooldown.
- Detail chart open behavior is intentionally unchanged in this Goal and remains a later guard Goal.
- `submitted=0` is preserved.
- Order, Router, Risk Guard, and Execution paths are not changed by this policy split.

## 15. AI-BRIEFING-BADGE-01 Implementation Note

`AI-BRIEFING-BADGE-01` improves the central briefing display without changing AI call timing.

Implemented policy intent:

- Briefing, reasons, and next actions display user-facing Korean copy instead of internal reason keys.
- Internal reason keys such as `change_ratio_normalized`, `momentum_neutral`, and `trade_value_very_strong` are translated only at display time.
- AI judgement source data is not rewritten by the display translation.
- The central briefing card records and displays the generation-time engine badge.
- Badge labels remain:
  - GPT: `G`
  - Gemini: `g`
  - LOCAL: `L`
- Badge colors follow the existing engine UI color family: GPT blue, Gemini purple, and LOCAL green.
- Status refresh does not replace the existing briefing engine badge.
- AI analysis refresh can update the badge when it creates a new briefing.
- Detail chart open behavior is intentionally unchanged in this Goal and remains a later guard Goal.
- `submitted=0` is preserved.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 16. MANAGED-TAB-REFRESH-DISPATCHER-01 Implementation Note

`MANAGED-TAB-REFRESH-DISPATCHER-01` makes the top status refresh button dispatch by the currently selected main tab.

Implemented policy intent:

- Status refresh is a tab-scoped display/data refresh.
- Status refresh does not schedule GPT/Gemini recommendation reinforcement.
- The AITS managed tab refreshes Basic/local managed rows, scanner rows, and the current center display only.
- The trade log tab refreshes the trade log display when a refresh method exists; otherwise it reports display-only status.
- The investment tab refreshes the investment display through the existing tab refresh method; it does not add a new balance/API path.
- The AI policy center refreshes policy/UI display state only.
- Common settings refresh updates saved/displayed engine state only and does not run connection tests.
- The explicit AI analysis refresh button remains the owner of manual AI judgement requests.
- Detail chart open behavior is intentionally unchanged in this Goal and remains a later guard Goal.
- `submitted=0` is preserved.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 17. DETAIL-CHART-AI-PREVIEW-GUARD-01 Implementation Note

`DETAIL-CHART-AI-PREVIEW-GUARD-01` blocks automatic GPT/OpenAI Preview calls when a detail chart is opened.

Implemented policy intent:

- Detail chart open is not an AI call trigger.
- Detail chart open does not call GPT, Gemini, OpenAI, or any paid Provider/API path.
- The existing GPT Preview builder remains available for a future explicit Preview refresh button.
- Detail chart open displays last-known AI analysis when session data exists.
- If no last-known AI analysis exists, the detail chart displays an AI Preview placeholder.
- Guard logs report `api_call_allowed=False`, `api_call_attempted=False`, `order_allowed=False`, and `submitted=0`.
- The top AI analysis refresh button remains the explicit AI judgement request path.
- The status refresh dispatcher is unchanged by this guard.
- Engine badge policy remains generation-time based.
- A future `DETAIL-CHART-AI-PREVIEW-BUTTON-01` Goal may add an explicit detail-chart Preview refresh button.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 18. MANAGED-TAB-SYNC-REFRESH-01 Implementation Note

`MANAGED-TAB-SYNC-REFRESH-01` makes the AITS managed-tab status refresh resynchronize scanner and managed scores.

Implemented policy intent:

- Managed-tab status refresh is Basic/local data synchronization only.
- Refresh obtains current market/scanner rows, copies market fields into managed rows, recalculates AITS Score v2, and redraws both managed and scanner tables.
- Managed rows no longer keep stale score input fields when matching scanner market data is available.
- Manual hold rows may recalculate score, but their trade status remains `ManualHold` / `매매보류`.
- The refresh path logs managed/scanner counts and score-sync summary with `submitted=0`.
- Status refresh does not call GPT, Gemini, OpenAI, GPT Preview, or any paid Provider/API path.
- The explicit AI analysis refresh button remains the owner of manual AI judgement requests.
- Detail chart open Preview guard remains unchanged.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 19. MANAGED-TAB-SELECTION-SYNC-01 Implementation Note

`MANAGED-TAB-SELECTION-SYNC-01` makes the central analysis center follow the selected Managed Candidates row.

Implemented policy intent:

- Managed row selection stores one selected symbol/row/index state for the managed tab display.
- Chart, Current Condition, briefing, evidence, and next-action cards refresh from the same selected managed row.
- Selection changes are display synchronization only and are not AI call triggers.
- The briefing engine badge uses generation-time metadata when available and falls back to Basic/local display state when absent.
- Internal reason keys are translated for UI display instead of being shown as raw keys.
- Status refresh, AI analysis refresh, and detail-chart open policies are unchanged.
- `submitted=0` is preserved.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 20. AI-BRIEFING-QUALITY-01 Implementation Note

`AI-BRIEFING-QUALITY-01` separates Basic/local calculation summaries from generated AI judgement copy in the central analysis center.

Implemented policy intent:

- Managed-row click and chart review show Basic/local calculation summaries by default.
- Basic/local mode uses `계산 요약`, `계산 근거`, and `관찰 포인트` card titles.
- Generated AI analysis mode uses `AI 브리핑`, `AI 판단 근거`, and `AI 다음행동` card titles.
- Card badges distinguish Basic/local summaries from generated GPT/Gemini/LOCAL analysis.
- Generated AI analysis continues to use generation-time engine metadata; engine changes do not rewrite existing badges.
- Raw internal reason keys are translated or replaced with user-facing Korean fallback text.
- Basic/local mode may guide the user to use the explicit AI analysis refresh button for deeper interpretation.
- Managed-row selection, status refresh, and chart review are not AI call triggers.
- Background event-based AI calls are not implemented in this Goal and remain a later policy implementation.
- `submitted=0` is preserved.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 21. DETAIL-CHART-CONTRACT-01 Implementation Note

`DETAIL-CHART-CONTRACT-01` defines the first display contract for detail-chart ETA, WHY, briefing, evidence, next-action, and trade-plan copy.

Implemented policy intent:

- Detail chart display fields are classified by `detail_chart_display_contract.v1`.
- The contract separates Basic/local calculation summaries from last-known or explicitly generated AI analysis.
- Detail chart open remains a display action and is not an AI call trigger.
- ETA is not the next evaluation time; without AI output it is only a Basic/local observation window for the current scenario.
- WHY is split into managed interest reason, current-state reason, and user-facing summary.
- Next action and trade-plan copy remain observation guidance unless a separate Router/Execution contract exists.
- Trade-plan text must not be presented as an order signal when `is_order_signal=false` and `is_execution_plan=false`.
- The compact contract log reports schema, mode, source, ETA source, WHY source, and safety flags.
- `api_call_allowed=False`, `api_call_attempted=False`, `order_allowed=False`, and `submitted=0` are preserved.
- Provider/API payloads, Router, Risk Guard, Order, and Execution paths are not changed.

## 22. DETAIL-CHART-ETA-WHY-01 Implementation Note

`DETAIL-CHART-ETA-WHY-01` applies `detail_chart_display_contract.v1` to the detail-chart ETA, WHY, observation, next-action, and trade-plan wording.

Implemented policy intent:

- Detail chart wording now distinguishes Basic/local calculation summaries from last-known AI analysis.
- Basic/local mode uses calculation and observation wording rather than AI judgement wording.
- ETA is presented as an observation window, not the next evaluation time.
- WHY is displayed as managed reason, current-state reason, and waiting/observation points.
- Next-action and trade-plan copy remain observation guidance unless Router/Execution produces a separate execution contract.
- No detail chart AI Preview button is added in this Goal.
- Detail chart open remains a display action and is not an API-call trigger.
- GPT/Gemini/OpenAI calls, Provider payloads, Router, Risk Guard, Order, and Execution paths are not changed.
- `submitted=0` is preserved.

## 23. DETAIL-CHART-SOURCE-CONSISTENCY-01 Implementation Note

`DETAIL-CHART-SOURCE-CONSISTENCY-01` makes detail-chart AI-analysis state and execution-contract state explicit and separate.

Implemented policy intent:

- `최근 AI 분석 참고` means previously generated analysis exists and may be displayed.
- `최근 AI 분석 없음` means the detail chart is showing Basic/local calculation summary only.
- Missing Router/Execution contract is displayed separately as `주문 실행 계약 없음` or `Router/Execution 미적용`.
- User-added source rows are displayed as user-friendly copy, not raw `USER`.
- Internal display sources are not exposed directly on the user surface.
- ETA remains an observation window, not the next evaluation time or an execution schedule.
- Detail chart source consistency work is not an AI call trigger.
- Detail chart open still does not call GPT, Gemini, OpenAI, or Provider APIs.
- Router, Risk Guard, Order, and Execution paths are not changed.
- `submitted=0` is preserved.

## 24. DETAIL-CHART-MODE-UNIFICATION-01 Implementation Note

`DETAIL-CHART-MODE-UNIFICATION-01` is a display consistency patch and is not an AI-call trigger.

Implemented policy intent:

- The detail chart uses one `display_mode` for AI status, AI operation center, ETA, WHY, observation scenario, and execution notice.
- A screen must not mix `최근 AI 분석 없음` with `최근 AI 분석 참고`.
- A screen must not mix `계산 기반 관찰 구간` with `AI 관찰 ETA`.
- Last-known AI analysis is used only when the analysis can be tied to the selected symbol and has generation metadata plus analysis content.
- Ambiguous or stale global AI payloads fall back to Basic/local `basic_summary` display.
- Detail chart open remains a display action and does not call GPT, Gemini, OpenAI, or Provider APIs.
- AI analysis reference and execution contract remain separate concepts.
- Router, Risk Guard, Order, and Execution paths are not changed.
- `submitted=0` is preserved.

## 25. DETAIL-CHART-KR-POLICY-01 Implementation Note

`DETAIL-CHART-KR-POLICY-01` cleans up user-facing detail-chart wording and audits the per-symbol policy panel.

Implemented policy intent:

- Detail-chart user surfaces should not expose internal terms such as `submitted=0`, `Router/Execution`, `ETA`, `preset`, `Basic Preview`, `STAY`, or `AI scenario`.
- User UI translates internal safety state into Korean copy such as `실제 주문 없음`, `주문 실행 경로 미연결`, `관찰 예상 시간`, `운용 방식`, `계산 기반 참고`, `관망`, and `관찰 시나리오`.
- Logs and proof fields may keep internal names when useful for debugging.
- The per-symbol policy panel is treated as display/storage/audit only in this Goal.
- Per-symbol AI cadence override is documented as a future candidate and is not connected to timers or Provider/API calls.
- Per-symbol maximum weight is documented as a future candidate and is not connected to Risk Guard, Order, or Execution.
- Detail chart open remains a display action and does not call GPT, Gemini, OpenAI, or Provider APIs.
- Router, Risk Guard, Order, and Execution paths are not changed.
- `submitted=0` is preserved internally and shown to users as `실제 주문 없음`.

## 26. DETAIL-CHART-AI-SNAPSHOT-FRESHNESS-01 Implementation Note

`DETAIL-CHART-AI-SNAPSHOT-FRESHNESS-01` adds display-only freshness metadata for recent AI analysis snapshots in the detail chart.

Policy intent:

- Detail chart open remains a display action and is not an AI call trigger.
- If a recent AI analysis snapshot exists for the selected symbol, the detail chart may display it automatically.
- A recent AI snapshot is valid only when it matches the selected symbol and has actual analysis content plus generation metadata.
- If no matching snapshot exists, the detail chart stays in Basic/local calculation summary mode.
- The UI may show engine, generated time, elapsed time, source label, and freshness status.
- Freshness labels are display-only guidance for the user; they do not affect Router, Risk Guard, Order, or Execution decisions.
- No detail-chart AI refresh button, background AI timer, or Provider/API call is added in this Goal.
- `api_call_attempted=False`, `order_allowed=False`, and `submitted=0` remain the expected safety state.

## 28. MANAGED-TAB-REFRESH-ACTION-WIRING-01 Implementation Note

`MANAGED-TAB-REFRESH-ACTION-WIRING-01` clarifies the active paths for the managed-tab refresh actions.

Policy intent:

- Status refresh is a data/display refresh only and must not schedule GPT/Gemini/OpenAI analysis.
- Status refresh should give immediate user feedback when clicked and completion feedback after the managed/scanner tables are refreshed.
- AI analysis refresh is an explicit user request and may use the existing AI analysis scheduling path.
- AITS OFF does not by itself block display-only AI analysis refresh; the action remains unrelated to live orders.
- AI analysis refresh must require a selected symbol before scheduling analysis.
- Completed AI analysis results are stored as per-symbol recent snapshots for detail-chart display.
- Skipped or failed analysis should report a user-visible reason without exposing API keys, prompts, account data, or full payloads.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 29. MANAGED-TAB-REFRESH-ACTION-AUDIT-FIX-01 Implementation Note

`MANAGED-TAB-REFRESH-ACTION-AUDIT-FIX-01` audits and repairs the runtime action path for the managed-tab refresh buttons.

Policy intent:

- The visible managed-tab status refresh button must emit click-entry proof and user feedback before running its data-only refresh.
- Status refresh remains Basic/local display refresh only and must not schedule GPT, Gemini, OpenAI, or Provider calls.
- The visible managed-tab AI analysis refresh button is an explicit user request and may use the existing AI analysis scheduling path.
- AITS OFF means automated trading is off; it does not block display-only explicit AI analysis.
- Manual AI analysis requests may bypass same-context or cooldown suppression, but not an in-flight request.
- Completed AI analysis results are stored as symbol-specific recent snapshots for detail-chart display.
- Skips, failures, and in-flight waits should be visible to the user without exposing API keys, prompts, account data, or full payloads.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 30. MANAGED-TAB-LIVELOG-WIRING-01 Implementation Note

`MANAGED-TAB-LIVELOG-WIRING-01` restores user feedback through the existing managed-tab Live Log surface.

Policy intent:

- Status refresh and AI analysis refresh should write click, progress, completion, skip, and failure feedback to the existing Live Log.
- No separate recent-action status label is introduced.
- Live Log append failures are recorded through safe proof logs without exposing prompts, API keys, account data, or payload bodies.
- Status refresh remains a Basic/local display refresh and is not an AI call trigger.
- AI analysis refresh remains an explicit user request and is unrelated to order execution.
- Completed manual AI analysis may store a symbol-specific snapshot and report that it can be checked in the detail chart.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 31. DETAIL-CHART-AI-PREVIEW-BUTTON-01 Implementation Note

`DETAIL-CHART-AI-PREVIEW-BUTTON-01` adds an explicit AI analysis refresh button inside the detail chart.

Policy intent:

- Detail chart open remains display-only and is not an AI call trigger.
- The detail-chart AI analysis refresh button is an explicit user request for the current symbol.
- The button reuses the existing managed-tab AI analysis refresh path and does not create a direct Provider/API client path.
- GPT/Gemini may incur API calls only after this explicit click.
- The result is stored as a per-symbol snapshot and the open detail-chart contract may be reapplied.
- The button is unrelated to order execution; `order_allowed=False` and `submitted=0` remain the safety boundary.

## 32. DETAIL-CHART-AI-SNAPSHOT-METADATA-01 Implementation Note

`DETAIL-CHART-AI-SNAPSHOT-METADATA-01` prevents raw `unknown` engine metadata from appearing in the detail-chart recent AI snapshot display.

Policy intent:

- Recent AI snapshots should store available engine, provider, and model metadata.
- The user-facing detail chart must not display raw `unknown` as the analysis engine.
- GPT, Gemini, LOCAL, calculation-based, or a safe `엔진 확인 필요` fallback is used for display.
- Missing metadata is treated as an incomplete snapshot label, not as an order or execution signal.
- Snapshot metadata remains display-only and does not affect Router, Risk Guard, Order, or Execution.
- Detail chart open remains display-only and is not an AI call trigger.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 33. DETAIL-CHART-UI-POLICY-POLISH-01 Implementation Note

`DETAIL-CHART-UI-POLICY-POLISH-01` is a UI polish and symbol-policy wording update.

Policy intent:

- The detail-chart AI analysis refresh button remains an explicit user request and now uses clearer refresh/analysis affordance.
- Button wording and iconography do not imply buy, sell, order, or execution.
- Detail-chart layout changes do not change AI-call policy.
- The per-symbol policy panel remains display-only and a future design-candidate surface.
- Per-symbol reference strength, cadence candidates, and maximum weight controls are not connected to AI timers, Router, Risk Guard, Order, or Execution.
- Detail chart open remains display-only and is not an AI call trigger.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 27. DETAIL-CHART-AI-SNAPSHOT-WIRING-01 Implementation Note

`DETAIL-CHART-AI-SNAPSHOT-WIRING-01` connects completed AI analysis results to the detail-chart recent snapshot display.

Policy intent:

- Explicit AI analysis refresh may store a sanitized, per-symbol recent AI snapshot after the existing AI analysis publish path completes.
- The detail chart reads only already-generated snapshots; opening the chart is still not an AI call trigger.
- Snapshot lookup requires selected-symbol matching and falls back to Basic/local summary when no matching snapshot exists.
- Stored snapshot metadata is limited to symbol, engine/provider, generated time, source, briefing, reason, and next-action display text.
- API keys, prompts, account data, order payloads, and full raw provider responses are not stored in the snapshot cache.
- Snapshot freshness remains display-only and does not affect Router, Risk Guard, Order, or Execution decisions.
- No detail-chart AI refresh button, background AI timer, or Provider/API call is added in this Goal.
- `api_call_attempted=False`, `order_allowed=False`, and `submitted=0` remain the expected safety state.

## 29. MANAGED-TAB-REFRESH-ACTION-AUDIT-FIX-01 Implementation Note

`MANAGED-TAB-REFRESH-ACTION-AUDIT-FIX-01` audits the user-visible managed-tab refresh buttons from the actual button objects through handler entry, scheduling, publish, and snapshot display proof logs.

Policy intent:

- The visible `상태 새로고침` button has a stable object name/alias and logs `[AITS][RefreshActionProof]` immediately on handler entry.
- Status refresh remains Basic/local display refresh only and must not call `_schedule_aits_main_gpt_reco`, `_build_gpt_preview_output`, GPT, Gemini, OpenAI, or a new Provider/API client.
- The visible `AI 분석 새로고침` button has a stable object name/alias and logs `[AITS][AIAnalysisRefreshProof]` immediately on handler entry.
- AI analysis refresh is an explicit user request, may use only the existing explicit AI analysis scheduling path, and must show skipped/failed/scheduled/completed user feedback.
- AITS OFF is treated as automation/order OFF; display-only AI analysis may still run and must show `실제 주문 없음`.
- Completed AI analysis publishes may store sanitized per-symbol snapshots for detail-chart display.
- API keys, prompts, account data, order payloads, and full raw provider responses must not be exposed or stored in the snapshot proof path.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 34. DETAIL-CHART-AI-OUTPUT-SANITY-01 Implementation Note

`DETAIL-CHART-AI-OUTPUT-SANITY-01` sanitizes detail-chart AI output before user display.

Policy intent:

- Detail-chart AI output is filtered against the selected symbol before display.
- Foreign market symbols in AI text are replaced with current-symbol-safe wording.
- Raw action tokens such as `ENTER`, `BUY`, `SELL`, `EXIT`, and `STAY` are displayed as AI reference opinions, not execution commands.
- Order-like copy such as split-entry language is softened into review/observation conditions.
- Engine/model labels are normalized so GPT models display as GPT, Gemini models display as Gemini, and LOCAL/basic stays separate.
- Detail chart open remains display-only and is not an AI call trigger.
- The AI refresh button still reuses only the existing explicit AI analysis path.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 35. AI-POLICY-CENTER-UI-SSOT-01 Implementation Note

`AI-POLICY-CENTER-UI-SSOT-01` clarifies AI Policy Center wording and global policy ownership.

Policy intent:

- The AI Policy Center is the global AI policy preview and save surface for AITS.
- User-facing `Preview` wording is shown as `미리보기`.
- `AI 주도형` is softened to `AI 우선 분석형`.
- `균형형` is shown as `균형 분석형`.
- `사용자 통제형` is shown as `사용자 확인 우선형`.
- `AI 관여 수준` is shown as `AI 판단 참고 강도`.
- Low, standard, and high involvement are shown as conservative, basic, and active reference strength.
- `LOCAL 데이터 정책` is shown as a local data management policy, not as a LOCAL engine selector.
- Policy Center save updates preview policy state only; it does not place buy, sell, liquidation, or order actions.
- Budget and daily-loss fields are preview/reference values and are not connected to Risk Guard, Order, or Execution in this Goal.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 36. INVESTMENT-TAB-POSITION-SOURCE-WIRING-01 Implementation Note

`INVESTMENT-TAB-POSITION-SOURCE-WIRING-01` connects the Investment tab position display to a read-only holdings source.

Policy intent:

- The Investment tab may refresh read-only position rows from existing parent caches or the existing `fetch_live_holdings` path.
- The tab distinguishes real empty holdings from source failure or unavailable state in user-facing copy.
- If account summary implies non-cash holdings but the position source returns no rows, the tab treats it as a source mismatch rather than as real empty holdings.
- Runtime feedback also rechecks the account-summary/position mismatch so a later empty-table render cannot mask a source mismatch as real empty holdings.
- `InvestmentCenterTab` owns the final table/composition/risk source-status messages; `app_gui.py` post-processing must not overwrite those owner messages when the owner state is present.
- Portfolio composition, risk summary, and selected-position detail share the same normalized read-only rows.
- Risk summary values that are not connected to Risk Guard remain placeholders and are not shown as enforced limits.
- This wiring does not call AI providers, does not create Provider/API clients, and does not change AI call policy.
- This wiring does not call Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 37. INVESTMENT-TAB-DUST-POSITION-FILTER-01 Implementation Note

`INVESTMENT-TAB-DUST-POSITION-FILTER-01` adds a display-only dust-position filter to the Investment tab.

Policy intent:

- The Investment tab keeps the original read-only position rows intact and filters only the rows shown in the table.
- Dust positions are hidden by default when their evaluation amount is below the display threshold, or when market data is unavailable and the row is marked as requiring market support review.
- Users can enable `먼지 종목 표시` to include those rows in the visible table.
- Portfolio composition and risk summary use the same visible rows as the position table.
- The filter does not delete holdings, create fake rows, or change account/holding source data.
- The filter does not call AI providers, does not create Provider/API clients, and does not change AI call policy.
- The filter does not call Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 38. INVESTMENT-TAB-COST-BASIS-VS-EVAL-01 Implementation Note

`INVESTMENT-TAB-COST-BASIS-VS-EVAL-01` separates cost-basis display from current market valuation in the Investment tab.

Policy intent:

- Average buy price is treated as cost-basis input and is not used as a current-price fallback.
- `cost_basis` is quantity multiplied by average buy price.
- `eval_amount` is quantity multiplied by a current market price only when a current price source is available.
- If current price is unavailable, current price, PnL, and return rate are shown as unavailable rather than calculated from average buy price.
- Portfolio composition clearly marks whether its center value is current-valuation based or cost-basis based.
- Risk summary uses the same visible rows and marks cost-basis-only weight as a reference basis.
- This display correction does not delete holdings, create fake rows, or change account/holding source data.
- This display correction does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 39. INVESTMENT-TAB-MARKET-PRICE-WIRING-01 Implementation Note

`INVESTMENT-TAB-MARKET-PRICE-WIRING-01` connects Investment tab position valuation to read-only market prices.

Policy intent:

- The Investment tab may look up current prices from existing market caches, scanner rows, or the existing read-only ticker helper.
- Current valuation, PnL, return rate, portfolio composition, and risk weight are calculated only when a read-only current market price is available.
- Average buy price remains cost-basis input and is never used as a current-price fallback.
- If current price lookup fails, the row remains cost-basis-only and user-facing copy says current price confirmation is needed.
- The read-only ticker lookup does not create an order client, does not call AI providers, and does not change AI call policy.
- This wiring does not call Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 40. INVESTMENT-TAB-RESPONSIVE-LAYOUT-PERSIST-01 Implementation Note

`INVESTMENT-TAB-RESPONSIVE-LAYOUT-PERSIST-01` persists Investment tab layout state.

Policy intent:

- The Investment tab stores table column widths and splitter sizes in existing `ui_state`.
- The footer save button treats Investment tab layout changes as a save target.
- Table rows use a compact default height; long memo text remains available through cell tooltips.
- Saved column widths and splitter sizes take precedence over default layout values on restart.
- The top KPI PnL remains account-summary based, while position row PnL remains position-valuation based; this Goal only clarifies copy.
- This work is UI persistence only and does not change balances, position valuation formulas, or read-only market price lookup logic.
- This work does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 41. INVESTMENT-TAB-DASHBOARD-RESTRUCTURE-01 Implementation Note

`INVESTMENT-TAB-DASHBOARD-RESTRUCTURE-01` reorganizes the Investment tab dashboard layout.

Policy intent:

- Portfolio composition is displayed as a compact top summary card beside the Investment tab KPI cards.
- Risk management is displayed as a compact summary beside the recent AI/position analysis summary.
- The main body is simplified to holdings table plus selected position detail.
- Existing position rows, dust filtering, valuation sources, column width persistence, and splitter persistence remain display-only UI behavior.
- This work does not change balance fetch, market price lookup, valuation formulas, AI call conditions, or provider behavior.
- This work does not call Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 42. INVESTMENT-TAB-RIGHT-COMPOSITE-PANEL-01 Implementation Note

`INVESTMENT-TAB-RIGHT-COMPOSITE-PANEL-01` groups the Investment tab right-side information into one composite analysis panel.

Policy intent:

- Portfolio composition, risk summary, and selected position detail are displayed as sub-sections inside a single right-side position analysis panel.
- The left side remains focused on KPI summary, recent AI/position summary, and the holdings table.
- Table dust filtering, compact row height, column width persistence, and splitter persistence remain intact.
- This work is a UI layout change only and does not change balances, holdings, market price lookup, valuation formulas, or AI call conditions.
- This work does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 43. INVESTMENT-TAB-RIGHT-PANEL-COMPOSITION-SIZE-01 Implementation Note

`INVESTMENT-TAB-RIGHT-PANEL-COMPOSITION-SIZE-01` adjusts the Investment tab right composite panel sizing.

Policy intent:

- The portfolio composition sub-card has a larger default height inside the right-side position analysis panel.
- The donut chart uses larger display bounds and remains controlled by the right-side splitter.
- Very small restored right splitter sizes fall back to the safer default ratio.
- This is a visual layout persistence adjustment only and does not change portfolio composition calculations, market price lookup, valuation formulas, or holdings source wiring.
- This work does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 44. INVESTMENT-TAB-METRIC-CONSISTENCY-01 Implementation Note

`INVESTMENT-TAB-METRIC-CONSISTENCY-01` clarifies Investment tab metric display bases.

Policy intent:

- Account-summary KPI PnL/return labels are distinguished from holdings-row valuation PnL/return.
- Holdings table weight, portfolio composition legend, risk summary weight, and selected-position detail weight share the same display row basis.
- Row weights are display-only percentages derived from existing valuation/cost-basis fields and account total; no new balance or market source is introduced.
- TP/SL text is compacted for table display only and is not connected to order policy.
- Current-price valuation copy references the last update context without changing price lookup or valuation formulas.
- This work does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 45. AI-SNAPSHOT-AUTO-CONDITION-AUDIT-01 Implementation Note

`AI-SNAPSHOT-AUTO-CONDITION-AUDIT-01` clarifies the meaning of automatic recent-AI snapshot storage.

Policy intent:

- `auto_condition` is a runtime snapshot-store source label, not an order signal.
- Snapshot storage itself does not call GPT, Gemini, OpenAI, Order Adapter, Execution Bridge, Router, or Risk Guard.
- Cost-capable provider calls remain limited to explicit user AI analysis refresh paths.
- Status refresh and detail-chart open must not create a new cost-capable AI provider call.
- Automatic runtime snapshots emit `[AITS][AISnapshotAudit]` proof logs with `api_call=False`, `cost_api=False`, `order_allowed=False`, and `submitted=0`.
- Repeated automatic snapshots with identical symbol/source/engine/provider/model/briefing/reason/next-action content are skipped; generated time alone does not force another store.
- Manual refresh snapshots are not deduplicated away, so explicit user analysis results remain visible.
- API keys, prompts, raw account payloads, and order payloads must not be logged by the snapshot audit path.

## 46. MANAGED-POOL-PERSISTENCE-SSOT-FIX-01 Implementation Note

`MANAGED-POOL-PERSISTENCE-SSOT-FIX-01` defines the managed symbol pool persistence owner.

Policy intent:

- Managed symbols are persisted in the existing prefs `ui_state.managed_pool_rows` key.
- The runtime owner remains `MainWindow.ai_managed_rows`; save writes a sanitized snapshot of that runtime list.
- `user_added` rows are preserved across app restart, including hold/status/score fields when available.
- The default `KRW-BTC`, `KRW-ETH`, and `KRW-XRP` fallback is used only when no saved managed-pool state exists.
- If a saved managed-pool state exists, the default fallback must not overwrite or append over the user's saved pool.
- Scanner/market candidate rows remain candidates until the user adds them to the managed pool.
- This persistence path does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- `order_allowed=False` and `submitted=0` remain the safety boundary.

## 47. TRADE-LOG-SHADOW-JOURNAL-WIRING-01 Implementation Note

`TRADE-LOG-SHADOW-JOURNAL-WIRING-01` connects Shadow/Preview AI decision records to the Trade Log Center as an observe-only journal.

Policy intent:

- Actual trade records remain sourced from the existing `recent_trades()` path.
- Shadow/Preview decision records are held in an in-app journal and merged into the Trade Log Center display adapter.
- Preview/Shadow records are typed separately from actual fills; actual fill counters count only fill records.
- Shadow/Preview rows display user-facing action/status labels such as `관망`, `진입 검토`, and `실제 주문 없음`.
- Journal rows are created after AI snapshot storage and include `order_allowed=False`, `submitted=0`, and `real_order=False`.
- Non-manual repeated runtime records are deduplicated by content signature; manual refresh records are preserved.
- This path does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- This path does not submit, create, buy, sell, liquidate, or modify orders.

## 48. TRADE-LOG-SHADOW-JOURNAL-PERSISTENCE-01 Implementation Note

`TRADE-LOG-SHADOW-JOURNAL-PERSISTENCE-01` persists the observe-only Trade Log Center journal and table layout.

Policy intent:

- Shadow/Preview journal rows are persisted under `ui_state.trade_log_shadow_journal_rows`.
- Trade Log Center column widths are persisted under `ui_state.trade_log_center_layout_state.column_widths`.
- The journal is capped at 500 observe-only rows and excludes actual fill records.
- Actual trade/fill records remain sourced from the existing `recent_trades()` path and are not mixed into the Shadow/Preview journal store.
- Restored journal rows contribute to Preview/Shadow counters and detail display, while actual fill counters continue to count only actual fills.
- Stored/restored journal rows preserve `order_allowed=False`, `submitted=0`, and `real_order=False`.
- This persistence path does not call AI providers, Order Adapter, Execution Bridge, Router, or Risk Guard.
- This persistence path does not submit, create, buy, sell, liquidate, or modify orders.

## 49. RUNTIME-AI-VISIBILITY-AND-COPY-FIX-01 Implementation Note

`RUNTIME-AI-VISIBILITY-AND-COPY-FIX-01` clarifies runtime AI-decision visibility and user-facing copy.

Policy intent:

- Runtime `ai.reco.updated` events can create recent-AI snapshots with `source=auto_condition`; this is classified as runtime-generated visibility, not a new provider/API call.
- Explicit user AI refresh remains distinguishable as `source=manual_refresh`.
- The Trade Log Center may journal runtime Shadow/Preview rows after snapshot storage, but the journal remains observe-only and does not connect to Router, Execution, Order, or Risk Guard.
- Trade Log detail display separates `판단 근거` from `사유`: the former is the compact system basis, while the latter is a user-readable explanation.
- If legacy rows have only one source text, the UI fallback expands one side so identical text is not repeated in both fields.
- User-facing copy should explain internal conditions in plain Korean while keeping internal keys, source labels, and log identifiers stable.
- Save-complete messages must state clearly that no real order was submitted.
- This work does not change AI provider call conditions, order actions, Router decisions, Risk Guard policy, or execution behavior.
- `order_allowed=False`, `real_order=False`, and `submitted=0` remain the safety boundary.

## 50. TRADE-LOG-USER-REASON-EXPLAINER-01 Implementation Note

`TRADE-LOG-USER-REASON-EXPLAINER-01` improves Trade Log detail explanations.

Policy intent:

- `판단 근거` remains a short decision basis summary.
- `사유` is a deterministic, user-readable explanation derived from the same observe-only journal row.
- Internal phrases such as hold-priority, candidate-priority, data/liquidity-limited, watch, undecidable, and entry-review states are expanded into plain Korean copy.
- The reason body should not mechanically repeat `실제 주문 없음`; order safety remains shown by the submitted/status fields and journal safety metadata.
- This is a display formatter only and does not change AI provider call conditions, Router action, Risk Guard policy, execution behavior, or actual trade storage.
- `order_allowed=False`, `real_order=False`, and `submitted=0` remain the safety boundary.

## 51. NETWORK-RECONNECT-UX-STATE-PROOF-01 Implementation Note

`NETWORK-RECONNECT-UX-STATE-PROOF-01` adds runtime proof for network lookup failure and recovery.

Policy intent:

- Network state is a runtime UI/check state, not an API-key or provider-selection state.
- The lightweight runtime state tracks `network_status`, `last_ok_at`, `last_failed_at`, `last_recovered_at`, `consecutive_failures`, and `last_checked_source`.
- Account, ticker, investment holdings, investment market-price, and investment refresh checks may report `check_failed`, `check_ok`, or `recovered` through `[AITS][NetworkState]`.
- Failure UI should tell the user that current values may be based on the last successful refresh.
- Recovery UI should make the next successful refresh visible as normal connection/recovery proof.
- This work does not change network retry policy, GPT/Gemini timeout behavior, AI provider call conditions, stale-decision policy, Router decisions, Risk Guard policy, or execution behavior.
- No raw account payloads, API keys, prompts, or order payloads are logged by the network-state proof path.
- `order_allowed=False`, `real_order=False`, and `submitted=0` remain the safety boundary.

## 52. NETWORK-RECONNECT-DATA-FEED-RECOVERY-FIX-01 Implementation Note

`NETWORK-RECONNECT-DATA-FEED-RECOVERY-FIX-01` separates provider/key status from market data feed health and adds candidate feed recovery proof.

Policy intent:

- Provider connection status describes AI provider/key verification only; market data health is tracked separately by `top_markets`/candidate-feed state.
- `top_markets` and ticker-empty results may mark the candidate feed as degraded/stale when the result is likely caused by a fetch failure or unavailable ticker data.
- Candidate feed stale state is user-facing: the UI can show that the candidate list is based on the last successful refresh.
- When the network recovers or the UI timer observes a stale feed, AITS schedules one observe-only candidate feed refresh with backoff.
- Candidate feed recovery refresh updates scanner rows, managed-row market fields, Basic score display, and related UI only.
- Candidate feed recovery does not run manual AI analysis refresh, GPT/Gemini/OpenAI calls, Router decisions, Risk Guard policy, or order execution.
- Recovery and stale logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 53. NETWORK-RECONNECT-CANDIDATE-UI-ACTUAL-RECOVERY-FIX-01 Implementation Note

`NETWORK-RECONNECT-CANDIDATE-UI-ACTUAL-RECOVERY-FIX-01` aligns candidate-feed recovery messages with actual scanner table rendering.

Policy intent:

- Candidate feed recovery is complete only after the candidate table renders rows and at least one visible row has a valid change-rate or score field.
- A network/ticker check returning `ok` may start candidate refresh, but it must not show candidate-list completion by itself.
- Incomplete recovery keeps the candidate feed in stale/degraded state and shows a retry/in-progress message instead of a success message.
- Manual status refresh and automatic network recovery use the same observe-only candidate feed refresh/render validation path.
- Duplicate recovery scheduling is guarded by pending/running flags and backoff.
- This recovery path does not run manual AI analysis refresh, GPT/Gemini/OpenAI calls, Router decisions, Risk Guard policy, or order execution.
- Recovery logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 54. STALE-AI-DECISION-GUARD-01 Implementation Note

`STALE-AI-DECISION-GUARD-01` adds display-only freshness labels for AI decisions and snapshots.

Policy intent:

- AI decision freshness is based on the decision/snapshot `generated_at` or journal timestamp, not network recovery time.
- Freshness display buckets are: fresh up to 10 minutes, recent/reference up to 30 minutes, stale after 30 minutes, and very stale after 60 minutes.
- Stale and very stale decisions must be shown as reference-only and should include a user-facing recheck/reanalysis warning.
- Recent AI cards, detail-chart AI snapshots, and Trade Log Shadow/Preview journal detail use the same freshness semantics.
- Network recovery must not promote an old AI decision to a fresh decision; it may only re-evaluate and log freshness.
- This is a display and observability guard only. It does not change Router action, Risk Guard policy, order submission, or execution behavior.
- Stale-decision order blocking, if needed, must be handled by a separate high-risk live-trading Goal.
- Freshness logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 55. STALE-AI-DECISION-VISIBILITY-FIX-01 Implementation Note

`STALE-AI-DECISION-VISIBILITY-FIX-01` makes display-only freshness labels visible and time-aware.

Policy intent:

- Freshness labels are recalculated from stored AI decision timestamps; recalculation does not call GPT, Gemini, OpenAI, or any provider.
- Detail-chart freshness updates are lightweight label updates for visible dialogs and must not trigger a full chart redraw.
- Recent AI and operation-center freshness labels may be refreshed by the existing UI timer as text-only updates.
- Trade Log Shadow/Preview detail rows show `판단 신선도` dynamically from the journal timestamp; restored rows are recalculated at selection time.
- Network recovery and candidate-feed recovery must not rewrite AI decision timestamps or promote old decisions to fresh decisions.
- This work does not change Router action, Risk Guard policy, order submission, execution behavior, or actual trade storage.
- Freshness visibility logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 56. DETAIL-CHART-AI-SNAPSHOT-LIVE-REFRESH-FIX-01 Implementation Note

`DETAIL-CHART-AI-SNAPSHOT-LIVE-REFRESH-FIX-01` wires stored AI snapshots to already-open detail charts.

Policy intent:

- After an explicit AI analysis refresh stores a per-symbol snapshot, an open detail chart for the same symbol may update its AI display contract immediately.
- The update is contract/text display only; it must not call GPT, Gemini, OpenAI, or any provider again.
- The update must not redraw the chart canvas or reintroduce full-render timer churn.
- `최근 AI 분석 없음 · 계산 기반 요약` is used only when no matching snapshot exists.
- Freshness labels continue from the stored snapshot `generated_at` and are updated by the display-only freshness timer.
- This work does not change Router action, Risk Guard policy, order submission, execution behavior, or actual trade storage.
- Live-refresh logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 57. AI-REFRESH-TIMEOUT-NONBLOCKING-FIX-01 Implementation Note

`AI-REFRESH-TIMEOUT-NONBLOCKING-FIX-01` moves explicit GPT/Gemini analysis refresh HTTP requests out of the Qt UI thread.

Policy intent:

- GPT/Gemini/OpenAI provider HTTP calls remain allowed only after an explicit user `AI 분석 새로고침` request.
- The provider worker performs only the HTTP request and returns a compact result; it must not read or mutate Qt widgets, Router state, Risk Guard policy, execution state, or order services.
- UI updates, AI snapshot storage, Trade Log Shadow/Preview journal wiring, and open detail-chart live refresh continue on the main thread through the existing result-apply path.
- Timeout or provider failure is shown as an analysis failure/reference-state message and must not be displayed as a successful AI judgement.
- Status refresh, stale-label refresh, network recovery, candidate recovery, and detail-chart open still do not start GPT/Gemini/OpenAI calls.
- Worker and failure logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 58. MANAGED-POOL-AI-REVIEW-SLA-FIX-01 Implementation Note

`MANAGED-POOL-AI-REVIEW-SLA-FIX-01` makes per-managed-symbol AI review freshness visible in the managed pool list.

Policy intent:

- Explicit user AI analysis refresh still targets the currently selected symbol only.
- All managed symbols continue to receive Basic/LOCAL calculation-based monitoring through managed-row score/status refresh.
- Managed rows display compact AI review SLA labels derived from the per-symbol AI snapshot timestamp: fresh up to 10 minutes, reference up to 30 minutes, stale after 30 minutes, and very stale after 60 minutes.
- Symbols without a stored AI snapshot show that AI review is missing/recheck-needed while Basic/LOCAL monitoring continues.
- SLA label refresh is display-only and recalculates from stored timestamps; it must not call GPT, Gemini, OpenAI, or any provider.
- Recheck-needed is an operational visibility label in this Goal, not a Router action change or order-blocking rule.
- This work does not change Router action, Risk Guard policy, order submission, execution behavior, or actual trade storage.
- Managed-pool SLA logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 59. MANAGED-POOL-AUTO-REVIEW-QUEUE-01 Implementation Note

`MANAGED-POOL-AUTO-REVIEW-QUEUE-01` builds an observe-only AI recheck candidate queue from managed-pool Basic/LOCAL monitoring.

Policy intent:

- The queue marks which managed symbols should be reviewed next; it does not call GPT, Gemini, OpenAI, or any provider.
- Queue triggers are display/operations signals such as missing AI review, stale or very stale AI review, score changes, price/volume changes when available, holding PnL movement, and stale market data.
- Holding rows receive higher queue priority than ordinary candidates when position risk/profit movement is visible.
- Manual-hold rows are not promoted into active review urgency unless another stronger signal exists.
- Queue output is user-facing through managed-row status text, Live Log, and `[AITS][ManagedPoolAIReviewQueue]` proof logs.
- The queue is not an order signal, Router action, Risk Guard rule, or execution plan.
- High-priority queue rows still keep `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 60. HOLDINGS-AI-REVIEW-PRIORITY-01 Implementation Note

`HOLDINGS-AI-REVIEW-PRIORITY-01` extends the observe-only review queue so real holdings receive priority even when they are not already present in the managed pool.

Policy intent:

- Holdings are read from existing investment/portfolio caches and are not auto-added to the managed pool.
- Managed-pool rows that match a holding receive higher queue priority for missing/stale AI review, PnL movement, price movement, stale market data, or target/stop proximity.
- Holdings outside the managed pool are surfaced as observe-only queue entries and Live Log guidance so the user can decide whether to register them.
- Dust positions may be lower priority, but the queue still keeps all entries observe-only.
- This queue never starts GPT, Gemini, OpenAI, Router, order, execution, or risk-management work.
- High-priority holding queue entries still keep `order_allowed=False`, `real_order=False`, and `submitted=0`.

## 61. MANAGED-TAB-AI-REFRESH-TARGET-SYMBOL-FIX-01 Implementation Note

`MANAGED-TAB-AI-REFRESH-TARGET-SYMBOL-FIX-01` fixes the explicit AI analysis refresh target owner for the managed tab.

Policy intent:

- The managed-tab `AI 분석 새로고침` target is the currently selected managed-table row at click time.
- The detail-chart `AI 분석 새로고침` target is the currently open detail-chart symbol.
- Restored login selection, legacy selected-symbol aliases, and the latest AI snapshot symbol are not request-target sources of truth when a managed-table row is selected.
- The request context freezes `target_symbol`, `decision_group_id`, source, and safety metadata before provider or LOCAL/Basic work starts.
- Async worker results, canonical contract metadata, per-symbol snapshot storage, and Trade Log Shadow Journal records use the frozen request symbol.
- If the user selects another row while the request is in flight, the result remains owned by the request symbol and must not overwrite the newly selected row's central display.
- Missing or invalid managed-row selection skips safely and does not start a provider call.
- This work does not change provider call frequency, Router action, Risk Guard policy, order submission, execution behavior, or actual trade storage.
- Target-resolution logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## AI Refresh Provider Provenance

`AI-REFRESH-PROVIDER-PROVENANCE-SYNC-FIX-01` fixes selected/actual engine provenance for explicit AI analysis refresh.

Policy intent:

- `provider_selected` is frozen once from the active engine selection at the click/request start moment.
- `provider_actual` is resolved from the actual worker or LOCAL/Basic fallback result.
- A later UI engine change must not rewrite the selected provider of an in-flight request.
- GPT/Gemini success records keep the invoked provider and invoked model.
- GPT/Gemini failure with Basic fallback keeps `provider_selected=gpt|gemini`, sets `provider_actual=local`, clears `invoked_model`, and marks `fallback_used=True`.
- LOCAL Basic records use `provider_selected=local`, `provider_actual=local`, and display as `LOCAL 계산 기반`.
- Configured model names and invoked model names remain separate; qwen/Ollama names are displayed only with actual invocation proof.
- This policy does not change provider call frequency, automatic AI refresh rules, Router action, Risk Guard policy, order submission, execution behavior, or actual trade storage.
- Safety metadata remains `submitted=0`, `order_allowed=False`, and `real_order=False`.

## AI Refresh Worker Result Delivery

`AI-REFRESH-WORKER-RESULT-DELIVERY-RUNTIME-FIX-01` makes the explicit GPT/Gemini refresh worker terminal path observable and recoverable.

Policy intent:

- A visible managed-tab `AI analysis refresh` click freezes the request group, target symbol, selected provider, and safety metadata before worker dispatch.
- GPT/Gemini workers emit exactly one compact terminal result for success, failure, or timeout; raw prompts, API keys, full HTTP bodies, account payloads, and order payloads are not logged.
- The main-thread result slot records `result_slot_enter`, then either publishes a provider success payload or a confirmed LOCAL calculation fallback for the same request group.
- A request is completed only after canonical publish reaches the `ai.reco.updated` apply path and snapshot/journal proof is recorded.
- If the event bus does not synchronously apply the payload, the same canonical payload is applied directly once; same-stage journal dedupe remains the duplicate guard.
- Watchdog completion uses the current request group terminal/apply state, not unrelated runtime LOCAL updates or global counters.
- Unrelated LOCAL/Basic side-channel payloads cannot consume or complete an active GPT/Gemini manual request.
- This work does not add automatic GPT/Gemini calls, change provider call frequency, promote Ollama, or touch Router, Risk Guard, execution, order submission, or actual trade storage.
- Worker delivery logs include `order_allowed=False`, `real_order=False`, and `submitted=0`.

## OpenAI Provider Call Truth And Usage Proof

`OPENAI-PROVIDER-CALL-TRUTH-AND-USAGE-PROOF-01` separates configured GPT state from actual OpenAI generation proof.

Policy intent:

- Stored keys and Preview/applied engine state are not evidence of an external AI judgment.
- Connection status may show `키 설정됨 · 호출 미확인`, `API 호출 중`, `API 응답 확인됨`, or failure classes; it must not claim a successful judgment from key presence alone.
- A GPT judgment can be displayed as `외부 AI 분석 성공` only when the explicit manual refresh worker records a provider call attempt, HTTP success, parsed response, response/request id, and provider success metadata.
- GPT failure with LOCAL fallback is displayed as `외부 AI 실패 · LOCAL 대체`, keeps `provider_selected=gpt`, sets `provider_actual=local`, and stores sanitized failure reason metadata.
- Dashboard cross-check reports should include KST/UTC request time, endpoint type, requested model id, HTTP status, masked response/request id, and token usage when available.
- This policy does not add automatic OpenAI calls and does not change Router, Risk Guard, Execution, Order, or actual trade storage.
- Safety metadata remains `submitted=0`, `order_allowed=False`, and `real_order=False`.

## OpenAI Model ID Compatibility

`OPENAI-MODEL-ID-COMPATIBILITY-FIX-01` separates the GPT preset display name from the actual OpenAI API model id.

Policy intent:

- `GPT-5.5 Instant` is the user-facing model display name.
- `chat-latest` is the current API request alias used for that preset.
- Legacy `gpt-5.5-instant` settings are normalized to `chat-latest` before dispatch and logged as `OpenAIModelConfig legacy_model_normalized`.
- `model_display_name`, `model_api_id`, `model_requested`, `model_returned`, and `invoked_model` remain distinct.
- The response `model` value is preserved as runtime proof but is not automatically written back as the saved setting.
- A successful GPT judgment still requires actual provider call proof; failed calls continue to use LOCAL calculation fallback with `submitted=0`, `order_allowed=False`, and `real_order=False`.


## Provider Connection Truth Error Diagnostics

`AI-PROVIDER-CONNECTION-TRUTH-ERROR-DIAGNOSTICS-01` separates configured keys, authentication checks, and generation response proof.

Policy intent:

- A stored OpenAI or Gemini key is not displayed as a successful generation connection.
- Startup/auth checks may show `?? ??? ? ?? ?? ???`; only a successful explicit generation response may show `?? ?? ???`.
- Gemini `error.status` is mapped before falling back to generic HTTP status: `INVALID_ARGUMENT` -> ?? ?? ??, `FAILED_PRECONDITION` -> ??/?? ?? ?? ??, `PERMISSION_DENIED` -> ?? ??, `NOT_FOUND` -> ?? ?? ??, `RESOURCE_EXHAUSTED` -> ?? ?? ??, `UNAVAILABLE` -> ??? ??, and `DEADLINE_EXCEEDED` -> ?? ?? ??.
- Provider failures can still publish LOCAL calculation fallback, but the record remains an external AI failure with `provider_selected` preserved and `provider_actual=local`.
- No automatic generation calls are added. Router, Risk Guard, Execution, Order, and actual trade storage remain unchanged.
