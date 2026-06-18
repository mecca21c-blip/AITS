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

