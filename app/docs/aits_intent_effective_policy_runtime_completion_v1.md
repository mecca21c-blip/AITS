# AITS Intent + Effective Policy Runtime Completion v1

## 목적

이 계약은 기존 전역 AI 정책과 종목 정책을 하나의 보수적인 Effective Policy로 해석하고, 같은 정책 식별자가 AI payload, 판단, Intent, 검증, 재판단, 복기와 학습 일지까지 이어지도록 한다.

Effective Policy는 행동이나 주문을 만들지 않는다. 선택 가능한 판단 범위와 확인 조건만 설명한다. AI가 판단하고 기존 Validator, Router, RiskGuard, LivePreflight와 Execution 경계가 그대로 적용된다.

## SSOT와 우선순위

원본 SSOT는 `ui_state.ai_policy_snapshot`, `ui_state.asset_policy_snapshots`, `strategy.ai_provider`, `orchestrator.execution_mode`, `managed_pool_rows`, `basic_config`다. Resolver는 별도 설정 SSOT를 만들지 않는다.

충돌은 안전 제약, 전역 정책, 종목 정책, preset, 명시 override, LOCAL 권한, Provider/CostGuard 순으로 해석한다. 노출·주문 한도는 더 작은 값, 현금 보유 조건은 더 큰 값을 선택하며 충돌 근거를 snapshot에 보존한다.

## Canonical Intent

`aits_ai_intent.v1`은 주문 예약이 아닌 관찰 계획이다. 목표, 예상 시나리오, 관찰 항목, 확인 조건, 무효화 조건, ETA, 정책 식별자와 revision을 보존한다.

상태는 proposed, active, revised, satisfied, invalidated, expired, completed, cancelled, blocked, inconclusive를 지원한다. 같은 decision/task/scope/revision은 중복 저장하지 않는다. ETA 만료와 invalidation은 parent intent를 유지한 새 재판단 revision을 만든다.

## 저장과 보존

파생 정책 상태는 `data/ai_policy/effective_policy_runtime_snapshot.json`과 `effective_policy_snapshots.jsonl`에, Intent 상태는 `data/ai_intent/active_intents.json`, `intent_history.jsonl`, `intent_summary.json`에 atomic write와 fsync로 저장한다. Decision, outcome, candidate, teacher와 정책 원본은 수정하지 않는다. observe-only summary는 이 파생 상태도 쓰지 않는다.

## 검증 계약

Validator는 allowed action, policy hash, policy conflict, ETA 범위, 필요한 invalidation, Intent의 주문 약속 금지를 확인한다. 외부 확인 필요 여부와 safe hold metadata를 반환하지만 주문을 생성하지 않는다.

현재 LOCAL_ENGINE은 Lv1/candidate_only다. 이 Sprint는 LOCAL final action, 자동 승격, 주문 경로 또는 안전 계층을 변경하지 않는다.

## UI

기본 화면은 현재 목표, 지금 보고 있는 것, 행동 조건, 계획 변경 조건, 현재 운용 성향, 다음 재확인 예상과 외부 AI 확인 필요 여부를 한국어로 표시한다. policy hash와 내부 상태명은 기본 화면에 노출하지 않는다.

## 정적 검증

`aits-intent-effective-policy-runtime-completion-v1-summary --observe-only`는 계약, lifecycle, payload/validator 연결, ETA/redecision parent linkage, Review 연결, 사용자 UI와 Lv1 안전 불변성을 검사한다. 이번 구조 Sprint에서는 앱 ON과 실제 runtime test를 수행하지 않는다.
