# AITS AI Decision Payload Quality Audit v1

## Feature Observability Follow-up

Goal 21 adds a privacy-safe feature manifest, freshness summary, quality grade, data-gap correlation, and structured invalidation shape counters. Training records retain the manifest summary rather than raw payload input. A payload hash proves identity; the manifest proves feature presence and value state without exposing secrets or the full prompt.

## 1. Audit Summary

The latest verified ON session completed the operational chain from initial seed through OpenAI response, validation, runtime-state registration, and ETA monitoring. All four initial decisions were `wait`; this was not a hardcoded action. The strongest evidence indicates that sparse market/indicator context combined with the provider prompt's explicit "choose wait or hold when data is insufficient" fallback produced the repeated conservative result.

The main audit limitation is material: runtime logs and `initial_management_decisions.jsonl` retain a payload hash and response metadata, but not a sanitized input-feature snapshot or per-field availability map. Consequently, actual values sent to OpenAI cannot be reconstructed after the call. This audit distinguishes runtime-proven facts from code-declared payload wiring.

Overall result: runtime decision transport is healthy, while payload observability, effective indicator coverage, structured invalidation conditions, portfolio action coverage, and user-facing explanation need improvement.

## 2. Runtime Session

- Runtime PID: `15752`
- ON start: `2026-07-12 18:48:08 KST`
- Initial seed session: `on-15752-1783849692`
- Provider/model: OpenAI / `gpt-4o-mini`
- Initial payloads: `KRW-BERA`, `KRW-BLAST`, `KRW-ENSO`, `PORTFOLIO`
- Provider responses: 4 received
- Validator results: 4 passed, 0 failed
- Runtime registrations: 4 decisions and 4 ETA states
- Orders and Managed Pool mutation: none

Runtime evidence proves task, symbol, payload hash, provider call, response action, confidence, ETA, invalidation list, validator result, and registration result. It does not prove the actual input feature values because neither logs nor training records retain a sanitized payload summary.

## 3. Position Payload Quality

The position builder declares quantity, average/current price, value, PnL, weight, target weight, holding age, four price-change windows, volume change, trade value, volatility, order-book imbalance, trade strength, RSI, MACD, moving averages, momentum, trend strength, portfolio limits, candidate alternatives, and constraints.

Several contract gaps remain. `source_type` and `dust` are not stored in the `position` object; `market.current_price`, `market_data_stale`, `portfolio.current_positions`, `managed_pool_symbols`, `prior_ai_decision`, and `eta_state` are absent. The builder reads indicators directly from the managed row and permits `null` or empty values without producing a field-availability summary. Actual runtime values therefore cannot be audited after execution.

| task | symbol/scope | position_complete | market_complete | indicators_complete | portfolio_complete | candidates_complete | constraints_complete | missing_critical_fields | quality_grade |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| position management | KRW-BERA | partial | unverified | unverified | partial | partial | partial | input snapshot, source type, dust, stale flag, prior/ETA state | C |
| position management | KRW-BLAST | partial | unverified | unverified | partial | partial | partial | input snapshot, source type, dust, stale flag, prior/ETA state | C |
| position management | KRW-ENSO | partial | unverified | unverified | partial | partial | partial | input snapshot, source type, dust, stale flag, prior/ETA state | C |
| portfolio management | PORTFOLIO | summary only | absent | absent | partial | partial | partial | market regime, indicators, opportunity gap, full action schema | C- |

`unverified` means the key is declared in code but its runtime value state was not persisted. It must not be interpreted as present and usable.

## 4. Portfolio Payload Quality

The portfolio payload includes holding summaries, Managed Pool symbols, total assets, available cash, operating cap, cap exposure/remaining amount, buy blocker state, scanner candidates, rotation candidates, external holdings, and a no-execution seed constraint.

It omits market regime and aggregate indicator context, holding-level average/current price and PnL KRW, candidate opportunity gap, prior decision/ETA state, and a sanitized feature availability map. Its `portfolio_actions` text mentions `rebalance` and `no_action`, but the validator-facing `allowed_actions` and output schema permit only `wait`, `hold`, `add`, `reduce`, and `rotate`. This mismatch narrows actual action coverage and makes the descriptive action list misleading.

## 5. Missing Feature Matrix

| feature | category | basic_can_compute | currently_in_payload | source_available | priority | recommended_fix |
|---|---|---:|---:|---:|---|---|
| Sanitized payload feature/value-state summary | E | yes | no | yes | P0 | Store field presence, null/stale status, units, and source without secrets or full prompt |
| RSI, MACD, moving averages, momentum, trend strength | A/E | yes | declared, runtime unproven | likely | P0 | Populate from indicator SSOT and record freshness/availability |
| Price change 1m/5m/15m/1h, volume change, volatility, trade value | A/E | yes | declared, runtime unproven | likely | P0 | Wire current market snapshot and record timestamps |
| Position source type, dust, market stale state | A | yes | incomplete | yes | P1 | Add explicit fields matching the decision policy contract |
| Current positions and managed symbols in position payload | A | yes | incomplete | yes | P1 | Include compact portfolio context for relative decisions |
| Weight, target weight, opportunity gap | A/E | yes | partial | yes | P1 | Record calculated values and source/freshness |
| Prior decision, ETA state, prior decision ID | A | yes | missing in initial payload/trace | yes | P1 | Carry decision lineage into initial and redecision records |
| Structured invalidation conditions | E | partly | position empty; portfolio free text | yes | P0 | Require typed condition, operator, threshold, unit, and source field |
| Execution plan and risk notes in training record | E | no computation needed | response not persisted | response has schema | P1 | Persist sanitized response contract fields |
| Order-book imbalance and trade strength | B | not reliably yet | declared, runtime unproven | unclear | P2 | Add source owner and freshness before relying on them |
| LIVE LOG reason/ETA/invalidation detail | A/E | yes | partial | yes | P1 | Render validated response summary tied to backend event ID |

Categories: A = BASIC can compute but payload coverage is missing or unproven; B = source not yet established; C = stale/unavailable; D = intentionally nullable; E = reinforcement required.

## 6. AI Response Quality

| task | symbol/scope | action | confidence | eta_seconds | reason_quality | invalidation_quality | execution_plan_quality | blocker |
|---|---|---|---:|---:|---|---|---|---|
| position management | KRW-BERA | wait | 0.6 | 3600 | low: generic data shortage | none | not auditable | missing structured conditions |
| position management | KRW-BLAST | wait | 0.7 | 3600 | low: same generic text as BERA | none | not auditable | missing structured conditions |
| position management | KRW-ENSO | wait | 0.7 | 3600 | low: no metric or threshold | none | not auditable | missing structured conditions |
| portfolio management | PORTFOLIO | wait | 0.7 | 3600 | low-medium: mixed performance stated without evidence | low: two free-text conditions | not auditable | conditions are not machine-specific |

The reasons are understandable Korean but do not cite prices, PnL, RSI, MACD, volume, volatility, cap, weights, or alternatives. Uniform 3600-second ETAs are valid but not demonstrably calibrated to each symbol. Execution plan and risk notes are not retained in the training record, so their quality cannot be assessed.

## 7. Action Coverage

Position management declares all nine core actions: `hold`, `wait`, `buy`, `add`, `sell`, `reduce`, `rotate`, `take_profit`, and `stop_loss`. The validator also enforces buy amount, sell ratio, and rotation target requirements for the applicable actions. Thus buy/sell/rotation are structurally possible.

Portfolio management is narrower: the effective schema allows only `hold`, `wait`, `add`, `reduce`, and `rotate`, despite the descriptive list also naming `rebalance` and `no_action`. There is no structured representation of "buy recommended but execution blocked"; the AI can explain it in `reason_ko` or `risk_notes`, but a buy action still requires a positive amount and later guards decide execution.

No runtime evidence in this session demonstrates `buy`, `sell`, `reduce`, `rotate`, `take_profit`, or `stop_loss`. The later redecision cycle produced both `hold` and `wait`, showing that action is not literally fixed to `wait`, but broad action coverage remains unproven.

## 8. ETA / Invalidation Quality

ETA registration and scheduler monitoring worked correctly. All four decisions registered 3600-second ETAs and produced tick/waiting events.

The three position decisions supplied no invalidation conditions. The portfolio decision supplied two natural-language strings: a rapid market change and emergence of a promising candidate. Runtime checks logged `expected=None`, `actual=None`, and `threshold=None`, so these conditions are not operationally measurable. A useful v1 condition should identify type, operator, threshold, unit, baseline, data source, and freshness requirement.

## 9. LIVE LOG / Status Bar Explanation Quality

Backend logs prove initial request, provider flow, validation, registration, ETA registration, and scheduler activity. `LiveLogUX` append events also occur during the flow. However, the structured audit logs do not retain the rendered Korean message body, and the training record does not connect a user-visible message ID to each decision.

The current evidence therefore proves event emission but not that users saw the specific `reason_ko`, ETA, and invalidation conditions. The generic reasons themselves would still answer "wait" without explaining what metric is missing, what is being watched, or what would change the decision.

## 10. Root Causes

1. Input observability gap: payload hashes are retained, but sanitized feature values and availability/freshness are not.
2. Data completeness gap: indicator and multi-window market keys are optional row lookups with no proof that runtime rows contain them.
3. Prompt fallback bias: the provider prompt explicitly selects `wait` or `hold` when evidence is incomplete; sparse context naturally converges on those actions.
4. Response contract weakness: invalidation conditions may be empty or unstructured natural language and still pass validation.
5. Portfolio schema mismatch: descriptive and effective action sets differ.
6. Explanation traceability gap: rendered LIVE LOG/status text is not auditable against decision ID and response fields.

The repeated waits are best classified as payload insufficiency plus conservative prompt fallback, not as a demonstrated market-specific judgment and not as a hardcoded action.

## 11. Fix Priority

1. Add a privacy-safe payload feature coverage record and freshness map for every provider request.
2. Populate and verify BASIC-computable market/indicator/weight/opportunity fields from named SSOT sources.
3. Strengthen invalidation output to a typed, machine-checkable schema while retaining readable Korean explanations.
4. Align portfolio requested actions with the validator schema and explicitly model proposal-versus-execution blocking.
5. Persist sanitized `execution_plan` and `risk_notes`, plus prior decision IDs, in training records.
6. Bind LIVE LOG/status summaries to decision ID, reason, ETA, and invalidation summary.
7. Add order-book/trade-strength sources only after ownership and freshness are defined.

## 12. Recommended Next Goals

1. `AITS-AI-DECISION-PAYLOAD-FEATURE-OBSERVABILITY-AND-FRESHNESS-FIX-21`
2. `AITS-BASIC-MARKET-INDICATOR-PAYLOAD-POPULATION-FIX-22`
3. `AITS-STRUCTURED-INVALIDATION-CONDITION-CONTRACT-FIX-23`
4. `AITS-AI-ACTION-COVERAGE-AND-PORTFOLIO-SCHEMA-ALIGNMENT-FIX-24`
5. `AITS-AI-DECISION-LIVE-LOG-EXPLANATION-TRACEABILITY-FIX-25`

The immediate next target should be Goal 21. Without payload observability, later quality changes cannot be proven against actual runtime calls.
## Population And Task Contract Follow-up

Goal 23 connects real cached candle and holdings/risk-budget sources to the payload. It also normalizes the legacy position task alias, expands insufficient-data phrase matching, and maps only safely measurable structured invalidation conditions. Quality improvement is evidence of better input coverage, not permission to trade.

## Invalidation Semantics And PID Scope Follow-up

Structured invalidation quality distinguishes supported, supported-partial, and unsupported conditions using semantic aliases and explicit reasons. Runtime quality evidence is scoped to the target application PID/session so a later dry-read process cannot replace the latest user-runtime result.

## MACD Exists And Visible Status Follow-up

MACD `exists` responses are measured as registered-but-not-triggerable when the feature is present. The status audit records safe Korean message samples so backend state and the intended UI explanation can be compared without dumping raw prompts or event dictionaries.

## ETA Redecision Context Follow-up

The F-grade redecision payload was caused by a minimal `current_state` path that did not inherit the initial management builders. Goal 36 aligns position redecisions with the position payload SSOT and portfolio redecisions with the portfolio payload SSOT, then adds prior-decision, ETA, invalidation, trigger, and sell-unit context. Final quality is scored after provider market/indicator population so pre-provider gaps cannot overwrite the actual request grade. Wait/hold correlation distinguishes missing-data explanations from market-condition decisions.
