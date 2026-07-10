# AITS AI Decision Trigger Policy v1

This policy defines when BASIC should ask AI to decide. Thresholds and indicators are triggers and payload evidence. They are not direct trade authority.

Role-injection summary:

- BASIC은 1~3초 단위로 시장/호가/체결/손익을 감시한다.
- BASIC은 10~30초 단위로 지표/후보/관리종목 상태를 갱신한다.
- BASIC은 이벤트가 발생하면 AI 판단 필요 여부를 만든다.
- LOCAL은 비용 없는 1차 판단자로 활용한다.
- GPT/GEMINI는 중요하거나 불확실하거나 실제 주문/로테이션 판단이 필요한 경우 호출한다.
- 외부 AI를 1초마다 호출하지 않는다.
- 외부 AI를 5분마다 무조건 호출하지 않는다.
- AI 호출은 판단 이벤트 기반이다.

## 1. BASIC Monitoring Cadence

- 1 to 3 seconds: price, orderbook, trade flow, and profit/loss movement monitoring.
- 10 to 30 seconds: RSI, MACD, moving averages, volume, volatility, managed pool, and candidate score refresh.
- 1 to 5 minutes: AI decision need review, ETA expiry, rotation candidate review, and portfolio rebalance review.

These cadences are observation and trigger cadences. External AI providers must not be called blindly on every cadence.

## 2. AI Call Method

- Do not call external AI on a fixed unconditional schedule.
- Use event-driven calls.
- Prefer LOCAL for frequent low-cost first judgment.
- Use GPT/Gemini for important, uncertain, or live-order decisions.
- If AI decision is required but the provider is blocked, BASIC must not place a fallback order.

## 3. Holding Decision Triggers

BASIC should request AI judgment when one or more of these events occurs:

- rapid profit percentage movement
- rapid loss percentage movement
- RSI overheat or depressed-zone entry
- MACD direction change
- rapid volume increase or decrease
- drop from recent high
- bounce from recent low
- ETA expiry
- invalidation of prior AI decision conditions
- take-profit, stop-loss, reduce, add, rotate, hold, or wait judgment needed

## 4. New Candidate Triggers

AI judgment can be requested when:

- trade value surges
- price change or volatility surges
- a scanner candidate is superior to existing managed names
- a new top scanner candidate appears
- a buy/add decision is needed and cash, cap, or risk constraints are active

## 5. Rotation Triggers

AI judgment can be requested when:

- an existing non-holding managed symbol loses momentum
- a new candidate gains momentum
- a rotation ETA expires
- portfolio weight needs adjustment
- cash or operating cap constraints require opportunity selection

Holding and protected symbols must not be rotated out without a separate AI decision and safety validation.

## 6. Portfolio Triggers

AI judgment can be requested when:

- cash is insufficient
- total operating cap is reached
- a symbol is overweight
- portfolio loss expands
- profitable holdings exist while stronger candidates appear
- portfolio exposure, available KRW, and target weights are inconsistent

## 7. AI Payload Required Fields

Every trade-affecting AI decision payload should include:

- position
- market
- indicators
- portfolio
- candidates
- constraints
- current policy
- requested decision
- output schema

The payload should carry profit/loss, RSI, MACD, volume, volatility, orderbook/trade strength when available, weight, target, ETA, cap, duplicate locks, dust status, and candidate alternatives.

## 8. AI Output Schema

AI output must include:

- action
- confidence
- reason_ko
- eta_seconds
- execution_plan
- sell_ratio, buy_amount_krw, or rotate_to_symbol when applicable
- risk_notes
- invalidation_conditions

Allowed actions are `hold`, `wait`, `sell`, `reduce`, `add`, `buy`, `rotate`, `take_profit`, and `stop_loss`.

## 9. AI Call Failure Policy

When AI decision is required but unavailable:

- BASIC must not place an arbitrary buy or sell.
- A blocker must be logged and shown.
- LOCAL fallback availability must be reported.
- Typical blockers include `ai_decision_required_but_provider_blocked`, `ai_decision_required_but_prompt_missing`, `ai_decision_response_missing`, and `ai_decision_invalid_schema`.

## 10. LOCAL Training Data Policy

Every AI decision cycle should store training data for future LOCAL improvement:

- input features
- AI decision
- confidence
- Korean reason
- execution result
- 5m, 15m, and 1h outcome placeholders
- realized PnL placeholder
- user override state
- provider
- payload hash

This record allows GPT/Gemini to act as teacher engines while LOCAL matures into a stronger offline decision engine.
