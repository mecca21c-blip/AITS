# AITS_SOURCE_MAP_v2

## Current Official Architecture

### 기준일: 2026-06

---

# 1. 프로젝트 정의

AITS는 단순 자동매매 프로그램이 아니다.

AITS의 최종 목표는:

> AI Asset Management Operating System

즉,

* 예측기
* 신호 발생기
* Rule Bot

이 아니라

시장 감시
→ 판단
→ 의도 공개
→ 행동
→ 복기
→ 정책 개선

을 수행하는 AI 자산운용 운영체제이다.

---

# 2. 핵심 철학

AITS는 예측을 약속하지 않는다.

AITS는 다음을 설명한다.

* 현재 무엇을 보고 있는가
* 무엇을 기다리고 있는가
* 왜 행동했는가
* 결과를 어떻게 해석하는가
* 무엇을 개선하려 하는가

사용자는 AI를 신호기로 보지 않는다.

사용자는 AI를 운용 매니저로 본다.

---

# 3. AI 엔진 철학

AITS의 엔진은 모두 동등하다.

엔진:

* GPT
* Gemini
* Local AI

Local AI는 테스트용 엔진이 아니다.

Local AI 역시 독립적인 운용 엔진이다.

현재 철학:

GPT = Gemini = Local AI

동등한 AI Runtime

Local AI는 장기적으로 AITS 전용 운용 엔진으로 발전한다.

Local AI의 목표는 범용 LLM 컬렉션이 아니다.

Local AI의 목표는:

- 코인 시장 이해
- 운용 전략 이해
- 복기 및 학습
- 비용 절감

에 특화된 독립 운용 엔진이다.

사용자는 내부 모델 구조보다
운용 성향과 결과에 집중한다.

---
# 3-A. Core Layer Architecture

AITS는 4계층 구조로 구성된다.

Layer 1
Basic Engine

Layer 2
AI Engine

Layer 3
Decision Router

Layer 4
Execution Layer

---

## Layer 1. Basic Engine

Basic Engine은 AI를 대체하기 위한 계층이 아니다.

Basic Engine의 목표는:

* 시장 데이터 수집
* 데이터 정규화
* 지표 계산
* 상태 분류
* 후보 생성
* 비용 절감

이다.

Basic Engine은:

* RSI
* MACD
* 거래량
* 거래대금
* 변동성
* 추세
* 위험도

등을 계산한다.

또한:

* 관심 종목 후보
* 로테이션 후보
* 손절 후보
* 익절 후보

를 사전에 정리한다.

Basic Engine은:

"무엇이 일어났는가"

를 정리한다.

Basic Engine은 직접 운용 결정을 내리지 않는다.

Basic Engine은 단순 계산기가 아니다.

Basic Engine은 다음 하위 계층으로 구성된다.

- Fact Engine
- Candidate Engine
- Risk Engine
- Portfolio Engine

Fact Engine:
시장 데이터를 수집하고 구조화한다.

Candidate Engine:
관심 종목 후보를 생성한다.

Risk Engine:
위험 종목, 손절 후보, 주의 종목을 탐지한다.

Portfolio Engine:
보유 자산, 현금 비중, 집중도, 포트폴리오 위험도를 분석한다.

Basic은 시장 정보를 구조화하고 후보를 압축한다.

Basic은 최종 운용 결정을 내리지 않는다.
---

## Layer 2. AI Engine

AI Engine은 AITS의 운용 의사결정 주체이다.

엔진:

* GPT
* Gemini
* Local AI

세 엔진은 동등한 운용 엔진이다.

AI의 역할:

* 관심 종목 선택
* 매수 판단
* 매도 판단
* 익절 판단
* 손절 판단
* 비중 조절
* 로테이션 판단
* 관망 판단

즉:

AI는

"그래서 지금 무엇을 해야 하는가"

를 결정한다.

AI는 단순한 해석 엔진이 아니다.

AI는 AITS의 운용 의사결정 주체이다.

AI의 책임:

- 무엇을 할 것인가
- 왜 그렇게 하는가
- 결과를 어떻게 해석하는가

즉:

AI는

Decision Engine
+
Reasoning Engine

이다.

AI는 Basic이 생성한 정보를 기반으로 최종 운용 결정을 내린다.

AITS에서 설명 가능한 판단
(Explainable Decision)은 핵심 설계 원칙이다.
---

## Layer 3. Decision Router

Decision Router는 결정자가 아니다.

Decision Router는 검증 계층이다.

역할:

* 정책 검증
* 위험도 검증
* 자금 검증
* 제약 조건 검증

AI의 판단을 검토한다.

---

## Layer 4. Execution Layer

Execution Layer는 집행 계층이다.

검증된 판단만 실행한다.

직접 AI가 주문하는 구조는 허용하지 않는다.

---

## Basic Engine과 AI Engine의 관계

Basic Engine은:

사실(Fact)을 생성한다.

AI Engine은:

그 사실을 기반으로 운용 결정을 내린다.

Basic Engine의 목표는:

AI를 제거하는 것이 아니다.

Basic Engine의 목표는:

AI가 가장 중요한 운용 판단에만 집중하도록

토큰 사용량과 운영 비용을 최소화하는 것이다.

즉:

100개 종목 전체를 AI가 분석하는 것이 아니라

Basic Engine이 먼저 후보를 압축하고

AI는 최종 운용 판단에 집중한다.

# 4. 현재 핵심 실행 흐름

run.py
→ AITSOrchestrator
→ AIDecisionService
→ DecisionRouter
→ AIEngineProvider
→ ExecutionBridge
→ OrderAdapter

주의:

AI는 직접 주문하지 않는다.

실제 주문은 반드시:

Risk Guard
→ Execution Layer

를 통과한다.

---

# 5. 현재 SSOT

## 5-1. 엔진 선택

strategy.ai_provider

허용값:

* local
* openai
* gemini

---

## 5-2. 실행 모드

orchestrator.execution_mode

---

## 5-3. Managed Pool

managed_pool_rows

---

## 5-4. AI 정책 Snapshot

ui_state.ai_policy_snapshot

---

## 5-5. 종목 정책 Snapshot

ui_state.asset_policy_snapshots

---

# 6. UI 계층

---

## 6-1. AI 정책 센터

과거:

전략설정 탭

현재:

AI 정책 센터

역할:

* 운용 스타일
* 리스크 수준
* 관망 성향
* AI 자율도
* Preset

사용자는 전략 작성자가 아니다.

사용자는 운용 철학 관리자다.

---

## 6-2. AI 운용 프로필

전역 정책

예:

* 초보 안정형
* 균형 운용형
* 단기 공격형
* 관망 스윙형
* AI 자율 극대형

---

## 6-3. 종목 운용 프로필

Managed Pool 종목 전용

저장:

asset_policy_snapshots

포함:

* 종목 성향
* 최대 투자 비중
* 자율도
* Override 정책

---

# 7. Policy System

구성:

전역 정책
+
개별 종목 정책

↓

Effective Policy

↓

Preview

현재는 Preview Only

Runtime 적용 없음

Order 적용 없음

---

# 8. Detail Chart Architecture

현재 구조:

[ 차트 ]
[ AI 브리핑 ]
[ AI 조정 Drawer ]

3-column 구조

사용자 조정 가능

QSplitter 저장

재실행 후 복원

---

# 9. AI 브리핑 센터

P15 완료

역할:

사용자가 10초 안에

"AI가 지금 무엇을 보고 있는가"

를 이해하게 만드는 계층

구성:

* 브리핑 헤드라인
* 시장 해석
* 운용 계획
* AI 시나리오
* 유지 예상

---

# 10. ETA 철학

ETA는:

다음 평가 시간 아니다.

ETA는:

현재 운용 시나리오 유지 예상 시간이다.

시장 변화 시:

언제든지 중간 재설정 가능하다.

---

# 11. AI Intent System

P16 진행 중

목표:

AI가 무엇을 기다리는지 공개

구성:

* 현재 목표
* 관찰 포인트
* 조건 설명

주의:

Intent는 주문 약속이 아니다.

Intent는 현재 AI의 관찰 전략이다.

---

# 12. AI Review System

P17 예정

목표:

왜 성공했고

왜 실패했는지 설명

---

# 13. AI Learning Journal

P18 예정

목표:

정책 변화 이력

학습 결과

반복 실패 패턴 기록

# 13-A. Local AI Learning & Data Governance

Local AI는 배포 후 스스로 진화하는 존재가 아니다.

Local AI는:

기록
→ 복기
→ 요약
→ 제안
→ 검증
→ 반영

과정을 통해 발전한다.

---

## Local AI Learning 원칙

Local AI는 다음 정보를 학습 자산으로 활용할 수 있다.

- 시장 데이터
- AI 판단
- 판단 이유
- Intent
- 실제 결과
- 손익 결과
- 복기 결과
- 정책 변경 이력

Local AI는 과거 운용 기록을 참고하여
유사 사례를 검색하고 비교할 수 있다.

---

## 정책 변경 원칙

Local AI는 정책 변경을 제안할 수 있다.

예:

- 거래량 단독 돌파 신뢰도 하향
- 특정 패턴 위험도 증가
- 특정 조건 우선순위 변경

그러나:

Local AI는 정책을 자동 적용하지 않는다.

모든 정책 변경은:

- 사용자 승인
또는
- Shadow 검증

을 거쳐야 한다.

---

## 데이터 관리 원칙

운용 데이터는 무한 저장하지 않는다.

장기 운영 시:

- 상세 로그
- 복기 로그
- Learning 데이터

가 지속적으로 증가할 수 있다.

따라서:

오래된 데이터는

- 요약
- 압축
- 보관 정책

을 적용한다.

---

## Data Governance

향후 제공 예정:

- 학습 데이터 보관 기간
- 저장 용량 제한
- 자동 요약
- Learning Journal 백업
- 데이터 초기화
- 학습 사용 여부

설정 기능

---

## Local AI 최종 목표

Local AI의 목표는

범용 LLM이 아니다.

Local AI의 목표는

AITS 전용 운용 엔진이다.

Local AI는:

- 코인 시장 이해
- 운용 전략 이해
- 실패 패턴 분석
- 정책 개선 제안

에 특화된다.

사용자는 내부 모델 구조보다

운용 성향
판단 품질
장기 성과

에 집중한다.
---

# 14. 실거래 안전 기준

명시적 승인 전까지 유지

* submitted=0
* AI 직접 주문 금지
* Risk Guard 우회 금지
* Execution Layer 우회 금지

---

# 15. 현재 개발 우선순위

P15
완료

AI 브리핑 센터

P16
진행

AI Intent System

P17
예정

AI Review System

P18
예정

AI Learning Journal

---

# 16. AITS 최종 비전

AITS는

"수익을 약속하는 AI"

가 아니다.

AITS는

현재 무엇을 보고 있고

왜 기다리고 있고

왜 행동했고

그 결과를 어떻게 해석하는지

사용자에게 설명하는

AI 자산운용 운영체제이다.

---
# 17. 공식 설계 원칙

1.
Basic은 Fact를 생성한다.

2.
AI는 Decision을 생성한다.

3.
Router는 Validation을 수행한다.

4.
Execution은 Action을 수행한다.

5.
AI는 반드시 판단 이유(Why)를 설명할 수 있어야 한다.

6.
AITS는 예측 정확도를 약속하지 않는다.

7.
AITS는 운용 의도(Intent)와 판단 근거(Reasoning)를 공개한다.

8.
AI는 운용 매니저이며 단순 신호 발생기가 아니다.

9.
ETA는 다음 평가 시간이 아니라
현재 운용 시나리오 유지 예상 시간이다.

10.
설명 가능한 판단(Explainable Decision)은
AITS 핵심 설계 원칙이다.