# AITS LOCAL_ENGINE Level 2 Co-Pilot Completion v1

## 목적

Level 2는 `Lv2 · 보조 판단자`이며 Authority code는 `co_pilot`이다. LOCAL_ENGINE은 후보 action, confidence, risk, abstention, escalation, 외부 교사 추천, ETA, invalidation과 근거를 Provider flow에 metadata로 제공한다.

Level 2는 final-action 권한이 아니다. GPT/Gemini의 유효한 응답 또는 기존 `local_safety_hold`가 final action을 결정한다. LOCAL_ENGINE은 OrderIntent, 주문, Managed Pool mutation을 만들지 않으며 RiskGuard, LivePreflight, CostGuard를 대체하거나 우회하지 않는다.

## Review reliability gate

AI 복기는 stage와 target별로 학습 가능성을 별도 계산한다.

- final: weight 1.0
- partial 1h: weight 0.8, action/capability 학습 가능
- partial 15m: weight 0.45, ETA 중심 제한 활용
- partial 5m: weight 0.25, 단기 판단 제한 활용
- pending/inconclusive/data unavailable: action label 학습 제외

판단 품질과 결과 품질 matrix를 함께 보존한다. `weak`와 `poor`는 negative action label이 아니다. 좋은 판단·나쁜 결과와 나쁜 판단·좋은 결과를 서로 뒤집어 학습하지 않는다.

Task별 feature contract를 적용한다. Position task에 candidate opportunity gap을 강제하거나 holding metadata 누락만으로 poor를 결정하지 않는다. Portfolio, buy, sell, rotation은 각 task에 관련된 missing feature만 reliability에 반영한다.

주요 파생 필드:

- `review_learning_eligible`
- `review_reliability_grade`
- `review_learning_weight`
- `review_stage_weight`
- `factual_evidence_score`
- `source_completeness`
- `review_target_eligibility`
- `review_exclusion_reasons`

## Learning Journal bridge

반복 성공·실패 pattern과 정책 제안은 action label이나 runtime policy가 아니다. 다음 maintenance 학습의 focus만 제공한다.

- priority task/action
- teacher sampling priority
- review-before-training gate
- Challenger 평가 focus
- retraining reason code

정책 제안은 사용자 검토 상태를 유지하며 자동 적용하지 않는다.

## Co-Pilot contract

Schema: `aits_local_engine_copilot_decision.v1`

Co-Pilot record는 Authority SSOT의 global/task/effective level을 포함한다. Level 1에서는 preview metadata만 생성하고 routing effect는 0이다. Level 2에서만 외부 AI 확인 우선순위와 provider recommendation이 routing context에 사용될 수 있다.

공통 안전 필드:

- `candidate_only=true`
- `applied_to_final_action=false`
- `final_action_unchanged=true`
- `local_final_allowed=false`
- `external_final_required=true`
- `riskguard_required=true`
- `livepreflight_required=true`
- `cost_guard_required=true`
- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `safe_for_live_expansion=false`

## Provider flow

Level 1:

1. LOCAL multi-head candidate 생성
2. Co-Pilot preview 생성
3. 기존 external routing 유지
4. Co-Pilot routing effect 없음

Level 2:

1. Co-Pilot uncertainty/risk/abstention과 review priority 확인
2. 외부 교사 확인 우선순위 또는 provider recommendation 제공
3. CostGuard가 외부 호출 가능 여부 결정
4. 유효한 external response가 final
5. 외부 호출 불가·무효이면 안전 보류

LOCAL candidate를 external response 대신 final로 사용하는 fallback은 없다.

## Eligibility와 사용자 승인

Task eligibility와 Global Level 2 eligibility는 Authority Policy SSOT의 threshold를 사용한다. UI와 provider code에 threshold를 복제하지 않는다.

Global eligibility가 false이면 현재 Level 1을 유지하고 blocker만 표시한다. True이면 `aits_local_engine_level2_promotion_candidate.v1` 후보를 만들 수 있다. 자동 승격은 금지하며 사용자 승인 전 state와 권한은 바뀌지 않는다.

승인 시 변경되는 것:

- LOCAL Co-Pilot metadata가 GPT/Gemini 확인 우선순위와 routing에 참여
- 승인된 eligible task의 capability가 Level 2로 전환

변경되지 않는 것:

- LOCAL 단독 final action과 주문 없음
- Champion 교체와 Level 승격은 별도
- RiskGuard, LivePreflight, CostGuard와 Execution submit path 유지

## UI

`AI정책센터 → 4. LOCAL_ENGINE 성장·운영`에 Lv2 준비도, 준비된 task, 학습 중 task, 학습 활용 가능 복기와 blocker 수를 표시한다. Promotion candidate가 있을 때만 `Lv2 전환 승인`과 `이번 Level 승격 보류`를 표시한다.

AI 복기 상세에는 후보 판단, 외부 확인 필요 여부, routing 사용 여부, task Level, Review reliability와 학습 활용 가능 여부를 표시한다. 학습 일지는 Level 2 준비 상태와 promotion history를 표시한다.

## Persistence boundary

Observe-only summary는 source, Review/Journal, Authority/Level/Champion을 쓰지 않는다. Review priority 파생 파일은 OFF/manual 복기 업데이트 또는 maintenance에서만 갱신한다. 사용자 승인 action만 Authority state를 변경한다.

## 검증

전용 mode:

`aits_qt_smoke_harness.py --mode local-engine-level2-copilot-completion-v1-summary --observe-only`

검증은 Review gate, Journal bridge, 실제 candidate 기반 Co-Pilot preview, Level 1 routing effect 0, task/global eligibility, 사용자 승인 계약, source hash, final-action mutation 0, 주문·Managed Pool mutation 0과 금지 계층 source diff를 확인한다.
