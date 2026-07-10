# AITS AI Decision Trigger Policy v1

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
