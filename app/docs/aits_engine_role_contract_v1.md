# AITS Engine Role Contract v1

This contract defines the authority boundary for AITS live operation.

## 1. BASIC Engine Role

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

## 2. BASIC Engine Prohibited Roles

BASIC must not perform these roles:

- direct sell decision from a single profit percentage threshold
- direct buy or sell decision from RSI/MACD alone
- direct buy or sell decision from volume alone
- rotation execution without AI decision authority
- RiskGuard or LivePreflight bypass
- direct OrderService, ExecutionBridge, OrderAdapter, or exchange submit outside the normal guarded path

If AI judgment is required but unavailable, BASIC must block or wait with an explicit blocker instead of inventing an order.

## 3. AI Engine Role

The AI engine is the final decision authority. AI engines include GPT, Gemini, and LOCAL.

The AI engine decides:

- buy
- sell
- hold
- wait
- rotate
- add
- reduce
- take_profit
- stop_loss

The AI engine also provides:

- ETA for next evaluation
- invalidation conditions
- Korean user-facing reason text (`reason_ko`)
- risk notes
- execution plan fields such as sell ratio, buy amount, or rotation target

## 4. LOCAL AI Role

LOCAL AI is the low-cost first decision layer. It may be called frequently for preliminary judgment and may become the long-term primary decision engine after enough GPT/Gemini teacher data and realized outcome data have been collected.

LOCAL must still return a structured AI decision. It must not be treated as BASIC fixed-rule trading.

## 5. GPT/GEMINI Role

GPT and Gemini are high-importance, high-uncertainty, and live-order decision engines. They are teacher engines for LOCAL training data and should be used when a real buy, sell, reduce, add, rotate, take-profit, or stop-loss decision needs stronger judgment than LOCAL can provide.

External AI calls are event-driven. They are not called every second and are not called on a fixed five-minute schedule without a decision event.

## 6. RiskGuard Role

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

## 7. LivePreflight Role

LivePreflight is the final pre-order verifier. It checks account, balance, quantity, market, preflight contract, and order readiness immediately before execution.

LivePreflight may block execution. It does not create the trading decision.

## 8. Execution Layer Role

The execution layer executes a validated order through the normal path. It does not decide whether an asset should be bought or sold.

The execution layer includes:

- DecisionRouter handoff/final action boundary
- ExecutionBridge
- OrderService
- OrderAdapter
- exchange adapter

## 9. UI / LIVE LOG Role

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
