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
