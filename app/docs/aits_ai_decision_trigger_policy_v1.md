# AITS AI Decision Trigger Policy v1

## Holdings Input Boundary

Position-management triggers and payloads use the normalized manageable-holdings snapshot. A missing PnL source is carried as a blocker and does not silently remove a real manageable holding. Dust balances are summarized separately and do not create management actions.

This policy defines when BASIC asks AI to decide. BASIC watches continuously, but AI calls are event-based. Indicators and thresholds are evidence for judgment, not direct order authority.

## 1. 핵심 원칙

- BASIC은 상시 감시한다.
- AI는 판단이 필요한 순간에 호출한다.
- 외부 AI를 1초마다 호출하지 않는다.
- 외부 AI를 5분마다 무조건 호출하지 않는다.
- AI 호출은 이벤트 기반이다.
- LOCAL은 비용 없는 1차 판단자다.
- GPT/GEMINI는 중요하거나 불확실하거나 실제 주문/로테이션 판단이 필요한 경우 호출한다.

기준 문장:

> BASIC은 계속 감시한다. AI는 판단이 필요한 순간에 호출한다. BASIC의 지표와 임계값은 판단 근거이며, 최종 행동 결정은 AI가 한다.

## 2. BASIC 감시 주기

### 1~3초

- 현재가
- 호가
- 체결 흐름
- 손익 변화
- 급등/급락 감지
- 상태바/LIVE LOG heartbeat

### 10~30초

- RSI
- MACD
- 이동평균
- 거래량 변화
- 변동성
- 관리종목 상태
- 후보종목 scanner

### 1~5분

- AI 판단 필요 여부 평가
- ETA 만료 확인
- 로테이션 후보 비교
- 포트폴리오 비중 재계산
- AI provider 호출 필요 여부 판단

## 3. 보유종목 AI 판단 trigger

- 수익률 급변
- 손실률 급변
- RSI 과열/침체 진입
- MACD 방향 전환
- 거래량 급증/급감
- 고점 대비 하락 시작
- 저점 대비 반등
- 목표 비중 초과/과소
- ETA 만료
- 기존 AI 판단 조건 무효화
- 보유종목의 시장/지표 상태가 기존 판단과 달라짐

## 4. 손절/위험 판단 trigger

- 손실률 확대
- 지지선 이탈
- 거래량 동반 하락
- 시장 전체 급락
- 호가 매수벽 약화
- 기존 AI 판단의 무효화 조건 발생
- 포트폴리오 전체 손실 확대

## 5. 신규 후보 판단 trigger

- 거래대금 급증
- 상승률 급등
- 거래량 동반 돌파
- 기존 관리종목보다 기회 점수 우위
- scanner 상위 신규 후보 발생
- 관리종목 max/cap 여유 발생
- 매도 후 현금 회수 발생

## 6. 로테이션 판단 trigger

- 기존 관리종목 모멘텀 약화
- 신규 후보 모멘텀 강화
- 기존 종목 ETA 만료
- 기존 종목 거래량 감소
- 신규 후보 거래량 증가
- 포트폴리오 비중 조정 필요
- 보유종목 일부/전량 매도 후 재배치 필요

## 7. ETA 판단 trigger

- ETA 만료
- ETA 기간 내 조건 위반
- 급등/급락
- 거래량 급감
- MACD/RSI 상태 변화
- 새 후보 등장
- 포트폴리오 조건 변화

## 8. 포트폴리오 상태 trigger

- 현금 부족
- 운용한도 도달
- 특정 종목 비중 과다
- 전체 포트폴리오 손실 확대
- 수익 종목은 있으나 신규 후보가 우위
- 신규 후보는 많으나 매수 여력 부족
- 매도 후 현금 회수 발생

## 9. AI 호출 우선순위

1순위:

- 실제 보유종목
- 손익 급변
- 익절/손절/전량청산 가능성

2순위:

- 로테이션 후보
- 보유종목보다 명확히 우위인 신규 후보

3순위:

- 관리종목 중 오래 판단 안 된 종목
- ETA 만료 종목

4순위:

- 단순 scanner 후보
- watch 후보

## 10. LOCAL / GPT / GEMINI 호출 정책

LOCAL:

- 30~60초 단위 또는 이벤트 발생 시 1차 판단 가능
- confidence가 높고 risk가 낮으면 LOCAL 판단 사용 가능

GPT/GEMINI:

- LOCAL confidence 낮음
- 실제 주문 판단 필요
- 로테이션 판단 필요
- 포지션 비중 큼
- 시장 급변
- BASIC 신호와 LOCAL 판단 충돌
- 최근 손실이 이어짐
- 사용자가 GPT/GEMINI 우선 모드 선택

Provider 호출 실패 시 BASIC이 임의 주문하지 않는다.

## 11. AI 판단 요청 payload 기본 구성

- task
- trigger_reason
- symbol
- position
- market
- indicators
- portfolio
- candidates
- constraints
- current_policy
- prior_ai_decision
- eta_state
- requested_decision
- output_schema

## 12. AI 판단 output 기본 구성

- action
- confidence
- reason_ko
- eta_seconds
- execution_plan
- sell_ratio
- buy_amount_krw
- rotate_to_symbol
- risk_notes
- invalidation_conditions

## 13. 금지 정책

- BASIC이 trigger를 action으로 오해하면 안 된다.
- 수익률/손실률/RSI/MACD/거래량은 판단 요청 근거이지 직접 주문 기준이 아니다.
- AI 판단 없이 buy/sell/rotate/add/reduce OrderIntent 생성 금지.
- AI 호출 실패 시 BASIC 임의 주문 금지.
- RiskGuard/LivePreflight 우회 금지.

Trigger는 action이 아니다. Trigger는 AI에게 물어볼 이유다.

## 14. 기준 문장

BASIC은 계속 감시한다. AI는 판단이 필요한 순간에 호출한다. BASIC의 지표와 임계값은 판단 근거이며, 최종 행동 결정은 AI가 한다.

## Buy Ready AI Gate

- Buy Ready is a trigger, not an action.
- BASIC creates `task=buy_decision` payload when Buy Ready is detected.
- AI must return a validated `buy` or `add` action before an executable buy OrderIntent can exist.
- If AI returns `hold` or `wait`, or the provider is blocked, BASIC records the blocker and waits.
- If AI schema validation fails, BASIC does not create an executable buy OrderIntent.

## Managed Pool Promotion AI Gate

- Managed Pool promotion is a decision event, not a simple scanner side effect.
- BASIC scanner candidates, scanner score, Basic score, normalized rotation score, trade value, and market rank are trigger evidence.
- Trigger evidence must be converted into `task=managed_pool_promotion_decision` before an automatic managed row can be added.
- AI may decide `promote`, `reject`, `wait`, `replace`, `rotate_review`, or `hold`.
- `promote` requires max-count room or a valid replace target. `replace` requires a removable, non-holding, non-protected row.
- `user_added`, `live_holding`, and `external_holding` are exception policies. They do not represent BASIC scanner promotion.
- If the provider is blocked, the response is invalid, or AI chooses wait/reject/hold, BASIC must not add the scanner candidate to the Managed Pool.
- Promotion decisions must be recorded for LOCAL training with payload hash, provider, AI action, confidence, reason, validator result, promotion result, blocker, and outcome placeholders.

## Rotation AI Decision Trigger Policy

- `normalized_rotation_score` and score gap are trigger evidence, not action.
- Rotation candidates must become `task=rotation_decision` payloads before replacement or future execution can proceed.
- AI may decide `rotate`, `wait`, `hold`, `replace`, `reduce_and_rotate`, or `reject`.
- `replace` requires a removable non-holding and non-protected target. Protected, user-added, live-holding, and external-holding rows are excluded from simple replacement.
- `rotate` and `reduce_and_rotate` are execution-pending decisions in this stage. They do not create immediate buy or sell submit.
- If provider response is blocked or invalid, BASIC records a blocker and does not rotate.
- Rotation decisions must be recorded for LOCAL training with old symbol, new symbol, payload hash, provider, AI action, confidence, reason, validator result, rotation result, blocker, and outcome placeholders.

## ETA And Invalidation ReDecision Policy

- ETA is a scenario watch period, not a pause or a direct action timer.
- BASIC records validated AI ETA, timestamps, payload hash, and invalidation conditions in runtime state.
- ETA expiry or a supported invalidation breach creates `task=ai_redecision` with the prior decision and observed state delta. BASIC never submits or mutates the pool directly.
- Provider-blocked or invalid redecisions remain waiting with an explicit blocker and are recorded in `redecision_events.jsonl` for LOCAL training.
## ETA Runtime Registration Coverage

ETA and invalidation monitoring begins only after a validated AI decision is registered. Buy, sell/position management, promotion, rotation, and redecision use the same registration contract. Provider-blocked or invalid responses are never active decisions. `hold`, `wait`, and `reject` responses with an ETA or invalidation condition are active watch states: BASIC monitors them and asks AI again when the scenario expires or becomes invalid, without converting the trigger directly into an action.
## ON Initial Management Trigger

The first active cycle of a new ON session is an event-based AI trigger. BASIC collects current holdings, Managed Pool, cash, operating cap, scanner candidates, constraints, and available indicators. It asks AI for position and portfolio management decisions and does not convert ON itself into buy, sell, reduce, add, or rotation action. Valid hold/wait responses also establish an ETA watch state. A blocked provider produces no action and may be retried after cooldown.
## Runtime Provider Decision Calls

- A runtime management provider call is an AI judgment request, not an order request.
- Verification and shadow one-shot guards do not own initial, position, portfolio, buy, sell, promotion, rotation, or redecision calls.
- The selected provider, key/model readiness, cost limit, payload validity, and duplicate cooldown remain mandatory.
- Only a real response that passes the AI Response Validator may be registered for ETA and invalidation monitoring.
## Runtime Decision Watch Registration

- A validated AI decision becomes active only after runtime-state store readback succeeds.
- `wait` and `hold` with a positive ETA remain active scenarios and must be reconsidered when ETA expires.
- Missing invalidation conditions do not cancel a valid ETA watch unless the validator rejects the response.
## Payload Feature Observability

Every AI decision request must have a feature manifest and freshness summary. BASIC reports whether each required feature is available, computed, null, missing, unavailable, or stale; it does not invent missing indicators or freshness. AI data-insufficiency reasons are correlated with this manifest. Safe previews are limited to numeric values and compact state/count summaries, with no raw prompt or API key material.

Invalidation conditions should use `condition_type`, `feature`, `operator`, `threshold`, `current_value`, `expected_direction`, and `reason_ko` so BASIC can determine whether a redecision trigger is measurable.
## Market And Indicator Evidence Population

BASIC may calculate RSI, MACD, moving averages, momentum, trend strength, price changes, volume change, and volatility from real candle history. Insufficient history remains unavailable. These values are AI judgment evidence only and cannot directly create buy, sell, reduce, or rotation actions.

The canonical position task is `position_management_decision`. Legacy aliases are normalized before provider validation. Supported invalidation conditions create redecision triggers only; unsupported conditions remain visible to audit and inert.
