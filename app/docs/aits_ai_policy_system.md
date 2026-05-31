# AITS AI Policy System

## 1. 핵심 철학

AITS는 단순 자동매매 봇이 아니다.

사용자는 전략 작성자가 아니라, "운용 철학 관리자"이다.

AI는 실제 시장 상태를 분석하고, 사용자가 설정한 운용 철학에 맞춰 운용 판단을 수행한다.

---

## 2. 기존 구조의 한계

기존 전략설정 기반 구조:

- RSI
- MACD
- 고정 손절/익절
- 룰 기반 조건식

은 기존 자동매매 봇 철학에 가깝다.

이 방식은:

- 설정 복잡도 증가
- 유지보수 어려움
- AI Runtime 철학과 충돌
- GPT/Gemini/Local AI 존재감 감소

문제를 만든다.

---

## 3. 새로운 구조

AITS는 다음 구조를 목표로 한다.

사용자:

- 투자 철학 설정
- 리스크 성향 설정
- 관망 성향 설정
- AI 자율도 설정

AI:

- Runtime 분석
- Reasoning
- Shadow Preview
- DecisionRouter Preview
- 실제 운용 판단

---

## 4. 정책 계층 구조

### [A] 전역 정책

위치:

- AI 정책 센터 탭

역할:

- 전체 AI 운용 철학 설정

예:

- 안정형
- 균형형
- 공격형
- AI 자율형

---

### [B] 개별 종목 정책

위치:

- 관리종목 상세 차트 창

역할:

- 특정 종목에 대한 override 정책

예:

- BTC = 안정형
- DOGE = 공격형

---

## 5. UX 철학

초보 사용자:

- 스타일만 선택

중급 사용자:

- 슬라이더 조정

고급 사용자:

- 고급 정책 펼치기 사용

AITS는 "설정앱"이 아니라 "AI 운용 시스템"처럼 동작해야 한다.

---

## 6. 메인 정책 요소

현재 핵심 정책:

- 운용 스타일
- 리스크 수준
- 관망 성향
- AI 자율도

향후 확장 가능:

- 회전 허용
- 추가매수 허용
- 최대 비중
- 손실 방어
- 신규진입 제한

---

## 7. Preview System과의 연결

정책 시스템은 다음 Preview 계층과 연결된다.

- Runtime Input
- Reasoning Preview
- Shadow Preview
- DecisionRouter Preview

예:

- "현재 BTC는 안정형 정책입니다."
- "AI는 관망을 우선합니다."

---

## 8. 안전 원칙

정책 시스템은:

- preview-only
- read-only
- no apply
- no order
- no inference trigger

원칙을 유지한다.

실제 order/apply 연결은 후기 고위험 단계에서만 수행한다.

---

## 9. 금지 사항

다음을 메인 UX로 사용하지 않는다:

- RSI 직접 입력 중심 UI
- MACD 직접 설정 중심 UI
- 복잡한 룰봇 스타일 조건식

이들은 "고급 정책" 영역으로만 제한 가능하다.

---

## 10. 최종 목표

AITS는 "사용자가 전략을 만드는 앱"이 아니라, "사용자가 투자 철학을 설정하고 AI가 실제 운용 판단을 수행하는 AI 자산운용 운영체제"를 목표로 한다.

---

## 11. 저장/복원 정책

AI 정책 센터의 전역 정책은 앱 재실행 후 유지한다.

저장 대상은 다음 네 가지이다.

- 운용 스타일
- 리스크 수준
- 관망 성향
- AI 자율도

저장된 정책 snapshot은 현재 단계에서 preview-only 데이터이다.

즉, 저장/복원은 UI 상태 유지 목적이며 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에는 적용하지 않는다.

정책을 실제 Runtime 판단이나 주문 적용 흐름에 연결하는 작업은 별도 Sprint에서 고위험 단계로 다룬다.

---

## 12. 개별 종목 정책 저장/복원

개별 종목 정책은 관리종목 상세차트 창에서 설정한다.

저장 단위는 종목 symbol이다.

저장 위치는 기존 설정 저장 흐름의 `AppSettings.ui_state["asset_policy_snapshots"]`이다.

현재 단계에서는 preview-only이며 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에는 적용하지 않는다.

전역 정책보다 개별 종목 정책이 우선될 수 있으나, 실제 적용은 별도 Sprint에서 진행한다.

---

## 13. 정책 Preview 연계

- 전역 정책과 종목별 정책은 Runtime, Reasoning, Shadow Preview에 read-only로 표시된다.
- 이 단계에서는 실제 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 주문 판단에는 적용하지 않는다.
- 종목별 정책이 "전역 정책 따름"이면 전역 정책을 effective policy로 표시한다.
- 종목별 정책이 지정되면 override로 표시한다.
- 모든 표시는 `preview_only=True` 원칙을 유지한다.

---

## 14. AI 운용 프로필 Preset 시스템

- 사용자는 slider를 직접 조정하지 않아도 preset 기반으로 AI 운용 성향을 선택할 수 있다.
- preset은 Runtime, DecisionRouter, OrderAdapter, ExecutionBridge, 실제 주문 경로에 직접 적용되지 않는다.
- 현재 단계의 preset은 UI 저장/복원 및 preview/reference 용도이다.
- slider 또는 정책 combo를 직접 변경하면 preset 상태는 "사용자 커스텀"으로 전환된다.
- 전역 preset과 종목별 preset은 독립적으로 존재할 수 있다.
- 종목별 preset도 현재는 preview-only이며 실제 Runtime/Router/Order 판단에는 적용하지 않는다.

---

## 15. Detail Chart Information Architecture

- 상세차트는 `차트 확인 → AI 현황 이해 → 필요 시 운용 조정` 흐름으로 구성한다.
- AI 판단, 판단 근거, 다음 행동, 시나리오, ETA는 "현재 AI 상태" 영역에 배치한다.
- 핵심 수치는 현재가, 목표가, 리스크 기준을 compact row로 표시해 우측 패널 과밀을 줄인다.
- 운용 프로필은 "사용자의 선택적 개입" 영역으로 분리한다.
- 운용 조정 영역은 접기/펼치기를 지원해 작은 화면에서 차트와 AI 현황을 우선 표시한다.
- 운용 조정 값은 preview-only 정책 시스템이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 16. Hidden Intervention UX

- AITS는 기본적으로 AI 자율 운용 구조를 지향한다.
- 사용자는 "운용 철학 관리자"이며 지속적 수동 조작자가 아니다.
- 상세차트의 운용 조정 영역은 기본적으로 collapsed 상태로 유지된다.
- 사용자는 필요 시에만 운용 조정 drawer를 펼쳐 개입한다.
- 상세차트 UX 흐름은 `차트 확인 → AI 상태 이해 → 필요 시 운용 개입` 순서를 따른다.
- Hidden intervention 구조는 차트 가시성과 AI 현황 우선순위를 높이기 위한 UI 정책이다.
- 운용 조정 값은 계속 preview-only이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 17. Right Drawer Intervention Architecture

- 상세차트에서 AI 현황과 사용자 개입 영역은 물리적으로 분리된다.
- AI 현황은 AI reasoning, 시나리오, ETA를 이해하는 상태 영역이다.
- 운용 조정은 사용자가 필요할 때만 여는 intervention 영역이다.
- intervention은 우측 side drawer 방식으로 제공된다.
- drawer open 여부와 관계없이 AI 현황 column은 독립적으로 유지된다.
- collapsed drawer는 차트 dominance와 작은 화면 가시성을 우선한다.
- 향후 고급 종목 정책은 drawer 내부 확장으로 처리한다.
- drawer 내부 정책 값은 계속 preview-only이며 Runtime, Router, Order에는 직접 적용하지 않는다.

---

## 18. Resizable Detail Layout Persistence

- AITS의 화면 관련 설정은 마지막 사용 상태를 복원한다.
- 상세차트는 차트 | AI 현황 | AI 조정 3영역으로 구성된다.
- 각 영역은 사용자가 splitter로 폭을 조정할 수 있다.
- 창 크기/위치/splitter 폭/drawer 상태는 AppSettings.ui_state에 저장된다.
- 해상도별 고정값을 찾기보다 사용자 환경에 맞춰 조정 가능한 구조를 우선한다.

---

## 19. Detail Status Card Resize Safety

- 상세차트의 AI 현황 영역은 내부 카드를 세로 splitter로 조정할 수 있다.
- AI 판단, 판단 근거, 다음 행동, AI 시나리오, AI ETA 카드는 각각 최소 높이를 유지한다.
- 긴 판단 근거와 시나리오 설명은 word wrap과 텍스트 선택을 허용해 잘림 위험을 줄인다.
- AI 현황 카드 높이 정보는 AppSettings.ui_state["detail_chart_layout_state"]["ai_status_splitter_sizes"]에 저장된다.
- 이 구조는 AI 판단/ETA/점수 계산과 주문/Runtime 적용 경로를 변경하지 않는다.

---

## 20. AI Reasoning Narrative Layer

- AITS는 AI의 판단 근거를 사람이 이해 가능한 문장으로 설명한다.
- Narrative Layer는 Runtime, Router, Order, apply 경로에 영향을 주지 않는다.
- Narrative는 AI 상태 설명용 브리핑 계층이며 preview-only 원칙을 유지한다.
- 판단 근거, 다음 행동, 시나리오, ETA는 불릿 나열보다 자연어 설명을 우선한다.
- 사용자는 AI가 무엇을 관찰하고 왜 기다리는지 이해할 수 있어야 한다.

---

## 21. Narrative Writing Guidelines

- Narrative는 운영자 브리핑이다.
- 장황한 설명보다 짧고 명확한 해석을 우선한다.
- AI 자기소개 표현을 사용하지 않는다.
- 상태 설명 → 해석 → 운용 계획 순서로 작성한다.
- Runtime Preview에는 요약형만 표시한다.

---

## 22. AI Briefing Center

- AI 브리핑 센터는 현재 AI가 보고 있는 시장 상황을 요약한다.
- 사용자는 AI의 상태를 10초 이내에 이해할 수 있어야 한다.
- 브리핑 센터는 Intent / Review / Learning 시스템의 상위 계층이다.
- ETA는 다음 평가 시간이 아니라 현재 운용 시나리오 유지 예상 시간이다.

---

## 23. AI Intent System

- AI Intent System은 현재 AI가 관찰 중인 운용 전략을 설명하는 UI 계층이다.
- Intent는 주문 약속이 아니며 Runtime, Router, Order, apply 경로에 영향을 주지 않는다.
- 브리핑 센터는 현재 목표, 관찰 포인트, 행동 조건을 표시한다.
- 현재 목표는 지금 우선 확인하는 방향을 요약한다.
- 관찰 포인트는 거래량, 시장 강도, 방향성처럼 판단 전 확인할 항목을 보여준다.
- 행동 조건은 어떤 조건이 충족되어야 다음 검토가 가능한지 설명한다.
- Intent는 preview-only/read-only이며 실제 판단 계산, confidence, ETA 계산을 변경하지 않는다.

---

## 24. AI Intent Reasoning Layer

- Intent는 상태 설명이 아니라 운용 의도이다.
- Intent는 현재 목표, 관찰 포인트, 행동 조건, 전환 후보로 구성된다.
- 현재 목표는 AI가 지금 기다리는 운용 방향을 설명한다.
- 관찰 포인트는 AI가 계속 확인 중인 조건을 2~4개 항목으로 공개한다.
- 행동 조건은 조건 충족 시 어떤 판단 후보로 재평가될 수 있는지 설명한다.
- Intent는 주문 약속이 아니며 매수/매도/주문 확정 표현을 사용하지 않는다.
- Intent는 Runtime, Router, Order, apply 경로에 적용되지 않는 preview-only 계층이다.
- 사용자는 Intent를 통해 AI가 무엇을 기다리고 어떤 조건을 중요하게 보는지 이해할 수 있어야 한다.

---

## 25. AI Intent UI Hierarchy

- AI 브리핑 센터 상단은 현재 요약을 담당한다.
- 상단 브리핑에는 상태 헤드라인과 1~2문장 요약만 둔다.
- AI Intent 영역은 별도 시각 블록으로 분리한다.
- Intent 블록은 현재 목표, 관찰 포인트, 행동 조건, 전환 후보를 구분해 표시한다.
- Review/Learning은 P17/P18 영역이며 P16에서는 보조 placeholder로만 작게 표시한다.
- Intent는 주문 약속이 아니라 현재 관찰 전략을 설명하는 preview-only 계층이다.

---

## 26. Detail Chart Role Separation

- AI 현황 column은 판단, 시장 해석, 운용 계획, Intent를 담당한다.
- AI 조정 column은 AI 시나리오, 유지 예상/ETA, 사용자 조정을 담당한다.
- 시나리오와 ETA는 AI가 제안하는 기본 운용값으로 표시한다.
- 사용자가 조정하면 향후 사용자 override 값으로 표시할 수 있다.
- 현재 단계에서는 preview-only이며 Runtime, Router, Order, apply 경로에 적용하지 않는다.
- 역할 분리는 우측 패널 과밀을 줄이고 판단/의도와 조정 영역을 분리하기 위한 UI 구조다.

---

## 27. Detail Chart Intent-first Layout

- AI 브리핑 센터는 AI Intent Center로 승격된다.
- 중앙 AI 현황 column은 Intent, AI 판단, 판단 근거만 담당한다.
- 시장 해석과 운용 계획은 별도 중복 카드로 유지하지 않고 판단 근거와 Intent에 흡수한다.
- 우측 AI 운영센터는 시나리오, 유지 예상/ETA, 사용자 조정, 고급 종목 정책을 담당한다.
- AI 조정은 종목별 사용자 개입 영역으로 상시 노출된다.
- 모든 내용은 preview-only이며 Runtime, Router, Order, apply 경로에 적용하지 않는다.

---

## 28. AI Operations Center Recovery

- 상세차트 우측 column은 Drawer가 아니라 고정 AI 운영센터로 사용한다.
- AI 운영센터는 AI 시나리오, 유지 예상/ETA, AI 조정, 고급 종목 정책 순서로 표시한다.
- AI 조정 영역에는 운용 프로필, 종목 성향, AI 자율도, 최대 투자비중, 기본값 복원을 상시 노출한다.
- 요약 박스는 현재 상태를 빠르게 확인하는 보조 정보이며 설정 UI를 대체하지 않는다.
- 이 구조는 preview-only이며 Runtime, Router, Order, Execution 경로에 적용하지 않는다.
