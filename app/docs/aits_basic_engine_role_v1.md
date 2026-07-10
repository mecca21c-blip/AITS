# AITS BASIC Engine Role v1

## 1. BASIC Engine 한 줄 정의

BASIC Engine은 판단자가 아니라 데이터 수집, 지표 계산, 후보 정리, AI 판단 요청, 실행 관리, 결과 기록을 담당하는 운영 관리자다.

기준 문장:

> BASIC은 계산한다. BASIC은 정리한다. BASIC은 AI에게 묻는다. AI가 판단한다. BASIC은 AI 판단을 안전하게 실행한다. BASIC은 결과를 기록해 LOCAL 학습 데이터로 쌓는다.

## 2. BASIC Engine의 핵심 역할

- Market Data Collector
- Account / Holdings Synchronizer
- Indicator Calculator
- Candidate Scanner
- Managed Pool Maintainer
- Position State Calculator
- AI Decision Trigger Detector
- AI Decision Payload Builder
- AI Response Validator
- Execution Coordinator
- Result Logger
- LOCAL Training Data Collector

## 3. BASIC Engine이 수집해야 하는 데이터

- 현재가
- 호가
- 체결 흐름
- 거래량
- 거래대금
- 캔들
- 변동률
- 시장 전체 흐름
- KRW 잔고
- 총자산
- 보유종목
- 평균매수가
- 현재 평가금액
- 주문 가능 수량

## 4. BASIC Engine이 계산해야 하는 보유종목 상태

- 보유수량
- 평균매수가
- 현재가
- 평가금액
- 손익금액
- 손익률
- 보유시간
- 현재 비중
- 목표 비중
- 먼지잔고 여부
- 매도 가능 수량
- 중복 주문 lock 상태
- 운용한도 여유

## 5. BASIC Engine이 계산해야 하는 지표

- RSI
- MACD
- 이동평균
- 단기 모멘텀
- 변동성
- 거래량 변화
- 거래대금 변화
- 고점 대비 하락률
- 저점 대비 반등률
- 체결 강도
- 호가 불균형
- 스프레드
- 슬리피지 예상

## 6. BASIC Engine이 발굴해야 하는 후보

- 거래대금 급증 종목
- 상승률 급등 종목
- 거래량 동반 상승 종목
- 기존 관리종목 대비 우위 후보
- 로테이션 후보
- 추가 편입 후보
- 제외 후보
- 외부 보유종목
- dust 제외 종목

## 7. BASIC Engine이 만드는 AI 판단 요청 trigger

- 수익/손실 급변
- RSI 과열/침체
- MACD 전환
- 거래량 급증/급감
- ETA 만료
- 기존 AI 판단 조건 무효화
- 로테이션 후보 발생
- 운용한도 변화
- 비중 초과
- 현금 부족
- 외부 보유종목 발견
- 신규 후보가 기존 관리종목보다 우위
- 포트폴리오 재배치 필요

BASIC은 “매도하라” 또는 “매수하라”를 만들지 않는다. BASIC은 “AI 판단이 필요하다”를 만든다.

## 8. BASIC Engine이 만들어야 하는 AI payload

- symbol
- position
- market
- indicators
- portfolio
- candidates
- constraints
- current_policy
- requested_decision
- output_schema

## 9. BASIC Engine의 AI 응답 검증 역할

- action 허용값 검증
- confidence 범위 검증
- sell_ratio 범위 검증
- buy_amount_krw 한도 검증
- rotate_to_symbol 후보 검증
- eta_seconds 유효성 검증
- reason_ko 존재 여부 검증
- invalidation_conditions 존재 여부 검증

## 10. BASIC Engine의 실행 관리 역할

- AI 판단 결과 수신
- RiskGuard 호출
- LivePreflight 호출
- ExecutionBridge / OrderService / OrderAdapter 정상 경로 전달
- submit 결과 수신
- post-order reconcile 요청
- duplicate lock 갱신
- LIVE LOG / status bar 갱신

## 11. BASIC Engine의 결과 기록 역할

- AI payload 저장
- AI response 저장
- 실행 여부 저장
- 차단 사유 저장
- 실제 주문 결과 저장
- 5분/15분/1시간 후 성과 추적
- LOCAL 학습 데이터 저장

## 12. BASIC Engine 금지 행동

직접 매수/매도 판단 금지:

- 4% 수익이면 직접 매도
- -10% 손실이면 직접 손절
- RSI 70 이상이면 직접 매도
- RSI 30 이하이면 직접 매수
- MACD 전환만으로 직접 매수/매도
- 거래량 급증만으로 직접 매수
- 점수 높음만으로 직접 매수
- normalized rotation score만으로 직접 교체
- AI 판단 없이 OrderIntent 생성
- AI 판단 없이 buy/sell/rotate/add/reduce 실행
- RiskGuard/LivePreflight 우회

## 13. BASIC Engine 기준 문장

BASIC은 계산한다. BASIC은 정리한다. BASIC은 AI에게 묻는다. AI가 판단한다. BASIC은 AI 판단을 안전하게 실행한다. BASIC은 결과를 기록해 LOCAL 학습 데이터로 쌓는다.

## BASIC Engine as Trigger Detector

- BASIC은 AI 판단 요청 이벤트를 만든다.
- BASIC은 trigger_reason을 생성한다.
- BASIC은 trigger를 직접 주문으로 변환하지 않는다.
- BASIC은 수익률, 손실률, RSI, MACD, 거래량, 변동성, 호가, 체결강도, ETA, 비중, 후보대안을 AI 판단 payload의 근거로 정리한다.
- BASIC은 trigger를 action으로 오해하지 않는다.
