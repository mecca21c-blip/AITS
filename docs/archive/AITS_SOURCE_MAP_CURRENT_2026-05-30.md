# AITS_SOURCE_MAP_v2026-06
# Current Official Source Map

최종 기준일: 2026-06
문서 역할: AITS 현재 구조, SSOT, 핵심 파일, 위험 구간, 다음 개발 방향을 정의하는 공식 소스맵

---

## 1. 문서 상태

이 문서는 현재 AITS 프로젝트의 공식 Source Map이다.

기존 문서:
- AITS_MASTER_STATUS.md
- 2026-04-03 기준 문서
- 현재 기준에서는 archive 문서로 취급한다.

주의:
- archive 문서는 참고용이다.
- 최신 개발 기준은 이 문서와 AITS 프로젝트 협업 규칙 v2026-06.1이다.

---

## 2. AITS 프로젝트 정의

AITS는 Python + PySide6 기반의 AI 자동매매 시스템이다.

구성:
- Upbit API
- PySide6 GUI
- Decision Router
- AI Engine
  - Basic
  - GPT/OpenAI
  - Gemini
- Risk Guard
- Execution Layer

최종 목표:

AITS를 AI 자산운용 시스템으로 완성한다.

---

## 3. 현재 개발 방식

현재 AITS는 수동 패치 프로젝트가 아니다.

현재 기준:
- Goal 중심 개발
- Codex Agent 중심 적용
- 파일 수 제한 없음
- Anchor 강제 없음
- 관련 파일은 Goal 범위 안에서 Codex가 탐색 가능
- 로그 분석은 Codex 담당
- 스크린샷 검증은 사용자 + ChatGPT 담당

과거 규칙 중 폐기된 항목:
- 한 번에 1파일만 수정
- 가능하면 app_gui.py만 수정
- UI 먼저, 로직 나중 고정
- Anchor 강제
- 사용자가 직접 코드 수정하는 방식 기준

---

## 4. 핵심 역할 분리

AITS는 KMTS/Core 위에 얹히는 판단 보강 레이어로 본다.

역할:
- KMTS Core = 실행과 리스크 관리
- AITS Layer = 종목 평가와 판단 생성
- UI = 설정 입력과 상태 표시
- Order Layer = 판단 결과를 실제 주문으로 변환

---

## 5. 현재 핵심 실행 흐름

기본 흐름:

run.py
→ AITSOrchestrator
→ AIDecisionService
→ DecisionRouter
→ AIEngineProvider
→ ExecutionBridge
→ OrderAdapter

중요:
- AI는 직접 주문하지 않는다.
- AI는 판단/검증/suggestion 역할이다.
- 실제 주문은 Risk Guard와 Execution Layer를 거쳐야 한다.

---

## 6. 주요 계층

### 6-1. UI Layer

주요 역할:
- 설정 입력
- 상태 표시
- Managed Pool 표시
- 종목 상세 표시
- AI 브리핑 표시

주요 파일 후보:
- app_gui.py
- config_tabs 관련 파일
- strategy_tab 관련 파일

주의:
- UI 표시값과 실제 엔진 입력값이 달라지면 안 된다.
- 중복 표시/중복 설정을 줄인다.

---

### 6-2. Orchestrator Layer

역할:
- 설정 상태 전달
- 실행 모드 관리
- 판단 루프 제어
- DecisionRouter와 실행 계층 연결

중요 SSOT:
- orchestrator.execution_mode

---

### 6-3. Decision Router Layer

역할:
- Rule/AI 판단 통제
- AI suggestion 저장
- final action 보호
- 로그/summary 생성
- shadow/dry-run 검증 흐름 관리

주의:
- final action 강제 변경 금지
- AI suggestion과 실제 action은 분리

---

### 6-4. AI Engine Layer

엔진 종류:
- Basic
- GPT/OpenAI
- Gemini

역할:
- Basic: 설정 기반 규칙형 판단
- GPT: 고급 판단/검증
- Gemini: GPT 대체 또는 보조 판단/검증

중요:
- 선택된 provider 기준으로만 동작
- Basic 선택 시 외부 API 호출 없음
- API key/model/payload 로그 노출 금지

---

### 6-5. Risk / Execution Layer

고위험 계층:
- OrderAdapter
- OrderService
- ExecutionBridge
- Risk Guard
- Live Trading 관련 코드

주의:
- 별도 Goal 없이 수정 금지
- 실거래 보호 조건 유지
- submitted=0 유지
- Risk Guard 우회 금지

---

## 7. SSOT 기준

현재 기준 SSOT:

### 7-1. 엔진 선택
strategy.ai_provider

허용값:
- basic
- gpt
- gemini

---

### 7-2. 실행 모드
orchestrator.execution_mode

---

### 7-3. Basic 설정
basic_config

역할:
- Basic 엔진 전용 판단 규칙
- 점수 계산 기준
- 진입/청산 기준
- 필터/쿨다운/민감도 기준

---

### 7-4. Managed Pool
managed_pool_rows

정의:
AITS가 실제로 분석하고 점수화하며 매매 후보로 삼는 종목 리스트

출처:
- system_default
- ai_selected
- user_added

중요:
출처와 관계없이 동일 파이프라인을 탄다.

---

## 8. Managed Pool 기준

Managed Pool에 포함된 종목은 반드시 다음 대상이어야 한다.

- 점수 계산 대상
- 상세 패널 대상
- 판단 후보 대상

금지:
- USER 종목만 점수가 없는 구조
- AI 종목과 USER 종목이 다른 파이프라인을 타는 구조
- 리스트 등록과 점수 계산이 분리된 구조

목표 구조:

Managed Pool 추가
= 점수 계산 등록
= 상세 표시 등록
= 판단 후보 등록

---

## 9. 탭 역할 기준

### 9-1. AITS 종목관리 탭

역할:
- Managed Pool 표시
- 종목 점수 표시
- 종목 상세 분석 표시
- Market Explorer ↔ Managed Pool 이동

하지 말 것:
- 엔진 선택
- 실행 모드 제어
- 전역 리스크 설정
- 주문 정책 설정

---

### 9-2. 투자현황 탭

역할:
- 잔고
- 보유 포지션
- 수익률
- 포지션 상태

---

### 9-3. 매매기록 탭

역할:
- 주문/체결/차단/실패 기록 표시

---

### 9-4. 전략설정 탭

역할:
- 공통 전략
- 공통 실행 정책
- 공통 리스크 정책
- 주문/실행 관련 상위 규칙

여기서 빼야 하는 것:
- Basic 전용 점수 기준
- Basic 전용 과열 제외
- Basic 전용 재진입 쿨다운
- Basic 전용 선별 강도

---

### 9-5. 공통설정 탭

역할:
- API 키
- 엔진 선택
- 모델 선택
- 연결 테스트
- Basic 엔진 설정
- 실행 모드 표시/제어

---

## 10. 현재 우선 개발 로드맵

현재 우선순위:

1. SSOT 정리
2. Managed Pool 분석 대상화
3. Basic 설정 단일화
4. 전략설정/공통설정 경계 분리
5. GPT/Gemini 판단 고도화
6. Risk Guard 강화
7. Live Trading은 마지막 단계

---

## 11. 현재 금지 구간

명시적 Goal 없이는 수정 금지:

- OrderAdapter
- OrderService
- ExecutionBridge
- Live Trading
- Risk Guard 우회 가능 코드
- 실제 주문 submit 경로

---

## 12. 실거래 안전 기준

명시적 승인 전까지 유지:

- 자동 실거래 금지
- submitted=0 유지
- AI 직접 주문 금지
- Risk Guard 우회 금지
- Execution Layer 우회 금지

---

## 13. 로그와 검증

로그 검증:
- Codex 담당

사용자 담당:
- 앱 실행
- 화면 확인
- 스크린샷 제공

ChatGPT 담당:
- 스크린샷 기반 UI 검증
- 다음 Goal 설계
- Codex 지시문 생성

---

## 14. 현재 문서 관리 기준

공식 최신 문서:
- docs/AITS_SOURCE_MAP_CURRENT.md
- docs/AITS_RULES_CURRENT.md
- AGENTS.md

archive 문서:
- docs/archive/*

주의:
archive 문서는 최신 지시 기준이 아니다.

---

## 15. 다음 작업 후보

다음 Goal 후보:

### Goal 1
AITS_SOURCE_MAP_CURRENT.md 생성 및 AGENTS.md 연결

### Goal 2
SSOT 현황 실제 코드 기준 점검

### Goal 3
Managed Pool user_added 점수 계산 파이프라인 검증

### Goal 4
Basic Config 중복 구조 확인 및 통합 계획 수립
