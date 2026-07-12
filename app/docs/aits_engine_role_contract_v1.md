# AITS Engine Role Contract v1

## Holdings Runtime SSOT

The BASIC engine normalizes live-account, investment-center, portfolio, and managed-row holding facts into one manageable-holdings snapshot. Status, SellEvaluation, initial AI position payloads, and Managed Pool holding protection consume that snapshot. Dust remains a reported balance but is not an AI-managed position. Missing PnL inputs block evaluation detail, not inclusion in the manageable target set.

This contract defines the authority boundary for AITS live operation.

## 1. BASIC Engine

The BASIC engine is not the final trading judge. It owns the operational plumbing:

- market, account, and holding data collection
- indicator calculation
- candidate scanning
- managed pool maintenance
- AI decision payload building
- AI response validation
- execution coordination after an AI decision
- decision and outcome logging
- LOCAL training data collection

BASIC may calculate profit/loss, RSI, MACD, volume, volatility, orderbook state, candidate rank, portfolio exposure, and ETA status. Those values are inputs to AI decision making, not final trade authority by themselves.

Korean authority sentence:

> BASIC은 계산한다. BASIC은 정리한다. BASIC은 AI에게 묻는다. AI가 판단한다. BASIC은 AI 판단을 안전하게 실행한다. BASIC은 결과를 기록해 LOCAL 학습 데이터로 쌓는다.

## 2. GPT/GEMINI/LOCAL AI Engine

GPT, Gemini, and LOCAL are AI engines. They own final decision authority for buy, sell, hold, wait, rotate, add, reduce, take_profit, and stop_loss.

LOCAL is the low-cost first decision layer and the long-term replacement candidate trained from GPT/Gemini decisions and realized outcomes. GPT/Gemini are high-importance, high-uncertainty, and live-order teacher engines.

## 3. RiskGuard

RiskGuard is the safety referee, not the trading judge.

RiskGuard validates:

- total operating cap
- duplicate order risk
- minimum order value
- available holding quantity
- position weight
- add-position cooldown
- symbol/global window caps
- sell duplicate locks

RiskGuard may block an AI decision, but it does not replace the AI decision.

## 4. LivePreflight

LivePreflight is the final pre-order verifier. It checks account, balance, quantity, market, preflight contract, and order readiness immediately before execution.

LivePreflight may block execution. It does not create the trading decision.

## 5. Execution Layer

The execution layer executes a validated order through the normal path. It does not decide whether an asset should be bought or sold.

The execution layer includes:

- DecisionRouter handoff/final action boundary
- ExecutionBridge
- OrderService
- OrderAdapter
- exchange adapter

## 6. UI / LIVE LOG

The UI and LIVE LOG explain the AI operating state to the user.

They must show:

- why AI judgment was requested
- what AI decided
- what AITS is waiting for
- ETA for the next review
- invalidation conditions
- RiskGuard/LivePreflight pass or block reason
- execution result if an order is submitted

User-facing messages must be Korean operational messages, not raw snake_case events.

## 7. LOCAL Training Store

The LOCAL Training Store records AI decision payloads, AI responses, execution results, blockers, and later outcome placeholders. It exists so LOCAL can learn from GPT/Gemini teacher decisions and actual operating outcomes.

## 8. 금지된 역할 침범 사례

BASIC must not perform these roles:

- direct sell decision from a single profit percentage threshold
- direct buy or sell decision from RSI/MACD alone
- direct buy or sell decision from volume alone
- rotation execution without AI decision authority
- RiskGuard or LivePreflight bypass
- direct OrderService, ExecutionBridge, OrderAdapter, or exchange submit outside the normal guarded path

If AI judgment is required but unavailable, BASIC must block or wait with an explicit blocker instead of inventing an order.

Directly forbidden examples include fixed profit-percent sell, fixed loss-percent stop-loss, RSI-only buy/sell, MACD-only buy/sell, volume-only buy, score-only buy, normalized-rotation-score-only replacement, AI-free OrderIntent creation, and RiskGuard/LivePreflight bypass.

## 9. 정상 판단/실행 흐름

BASIC Signal Collector
→ AI Decision Trigger
→ AI Decision Payload
→ AI Engine Decision
→ BASIC Response Validation
→ RiskGuard
→ LivePreflight
→ Execution Layer
→ Result Reflection
→ LOCAL Training Record
→ LIVE LOG / Status Update

## AI Decision Trigger Boundary

- BASIC is the trigger detector.
- AI is the final decision authority.
- Trigger is not action.
- Trigger는 action이 아니다.
- RiskGuard validates the safety of the AI action.
- LivePreflight validates the final order-readiness of the AI action.
- Execution executes. Execution does not decide.

## AI Response Validator And OrderIntent Metadata Boundary

- AI output must pass a shared response validator before BASIC can coordinate execution.
- Buy Ready is an AI decision trigger only.
- Buy/add OrderIntent requires validated AI metadata including provider, action, confidence, reason, ETA, payload hash, and validation result.
- RiskGuard and LivePreflight run after validated AI action; they are safety gates, not substitutes for AI judgment.
- If AI response is missing, provider is blocked, or schema validation fails, BASIC records the blocker and does not create an executable OrderIntent.

## Managed Pool Promotion Boundary

- Managed Pool promotion changes the AITS operating universe, so automatic promotion is an AI decision action.
- BASIC scanner candidates, scores, and quality gates may create a promotion trigger and payload, but they must not directly create an automatic managed row.
- `basic_added` scanner rows require validated AI promotion approval and promotion metadata. Approved automatic rows should be represented as `basic_added_ai_approved` or another explicit AI-promoted source.
- AI promotion actions include `promote`, `reject`, `wait`, `replace`, `rotate_review`, and `hold`.
- `user_added`, `live_holding`, and `external_holding` are exceptions because they are user-directed or account-truth holdings. Dust exclusion remains a safety filter.
- Promotion decisions and blockers are recorded for LOCAL training, including payload hash, provider, AI action, confidence, reason, validator result, promotion result, and outcome placeholders.

## Rotation Decision Boundary

- Rotation changes the managed universe or prepares future sell/buy execution, so it requires AI decision authority.
- BASIC may compute `normalized_rotation_score`, score gap, and rotation candidates, but those values are triggers and evidence only.
- AI rotation actions include `rotate`, `wait`, `hold`, `replace`, `reduce_and_rotate`, and `reject`.
- `replace` can only target a non-holding, non-protected, removable row. Protected, user-added, live-holding, and external-holding rows are not simple replacement targets.
- `rotate` and `reduce_and_rotate` are execution-pending decisions in the gate stage. They must not submit sell or buy orders until a later guarded execution goal connects RiskGuard, LivePreflight, and Execution.
- Rotation decisions and blockers are recorded for LOCAL training with payload hash, provider, AI action, confidence, reason, validator result, rotation result, and outcome placeholders.

## ETA And Invalidation Boundary

- BASIC watches ETA and invalidation conditions for validated AI scenarios. Expiry and condition breaches are AI redecision triggers, never direct trade or managed-pool actions.
- An `ai_redecision` payload contains the prior decision, current state, and delta since the prior decision.
- Provider failure remains blocked/waiting; the scheduler does not invoke RiskGuard, LivePreflight, or Execution.
## Initial AI Management Seed Boundary

ON activation requires BASIC to assemble the initial management context and ask the selected AI provider. AI remains the decision authority. The initial seed may register validated hold, wait, position-management, or portfolio-management scenarios for ETA/invalidation monitoring, but it never submits an order or mutates the Managed Pool by itself. Provider failure or schema failure leaves the seed blocked and records the reason for retry and training audit.
## Provider Call Boundary

- Provider call means “ask the selected AI to decide”; it never means “execute an order.”
- Verification-call controls and runtime-management-call controls are separate contracts.
- Runtime OpenAI/GPT calls require readiness and cost/duplicate guards, never expose key bodies, and feed only Validator and decision registration.
- Any later trade remains behind RiskGuard, LivePreflight, and the unchanged Execution Layer.
## Decision State Store Boundary

- Registration helper writes and ETA scheduler reads one runtime decision-state SSOT.
- A registered log must reflect an actual active state found by decision ID in that store.
- BASIC may monitor validated `wait` and `hold` states, but it may not convert ETA or invalidation events directly into orders.
## AI Payload Observation Boundary

BASIC owns factual feature availability and freshness metadata. It may compute and report payload quality, but a quality grade is not a trade action and does not replace AI judgment. Provider prompts and secret bodies are not audit output. Runtime training stores payload/manifest hashes and safe coverage summaries only. Missing or stale data may block or qualify a decision request, but never authorizes BASIC to create a buy, sell, or rotation action.
## BASIC Feature Population Boundary

BASIC owns factual market/indicator calculation from real runtime sources and reports source time and freshness. It does not synthesize missing candles, indicators, volume, price changes, or freshness. Payload quality and invalidation thresholds remain evidence and watch obligations, never final trading authority.

## Invalidation Watcher Boundary

BASIC may normalize and monitor AI invalidation conditions, but a triggered condition only requests AI redecision. Unsupported or partial conditions cannot produce buy, sell, rotate, promotion, or execution actions.
