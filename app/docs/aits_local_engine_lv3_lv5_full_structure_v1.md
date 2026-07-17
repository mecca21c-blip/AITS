# AITS LOCAL_ENGINE Lv3~Lv5 Full Structure v1

## 목적

이 문서는 LOCAL_ENGINE의 Lv3~Lv5 권한 구조를 정의한다. 현재 운영 권한은 Lv1 `candidate_only`이며, 이 구조의 추가만으로 상위 권한이 활성화되지 않는다.

## Level 계약

- Lv0 `external_only`: 외부 AI만 최종 판단한다.
- Lv1 `candidate_only`: LOCAL 후보 판단을 관찰하고 외부 AI가 최종 판단한다.
- Lv2 `co_pilot`: LOCAL이 위험·불확실성·교사 우선순위를 보조하지만 외부 AI 또는 안전 보류가 최종 판단한다.
- Lv3 `task_primary`: 사용자 승인 task/action 중 `wait`, `hold` 같은 비주문 판단만 LOCAL final 후보가 될 수 있다. 주문성 행동은 외부 확인이 필수다.
- Lv4 `local_primary`: 사용자 승인 task/action pair에서 LOCAL final 후보가 될 수 있다. Validator, RiskGuard, LivePreflight, 기존 Execution, Reconciliation은 항상 필수다.
- Lv5 `internal_asset_manager`: 승인·지원 범위에서 LOCAL 우선 판단을 허용하되 OOD, 고위험, 낮은 신뢰도, drift와 정기 감사 표본은 GPT/Gemini로 escalation한다.

## 권한 SSOT와 계산

Global Level은 `local_engine_authority_state`가 계속 소유한다. `local_engine_task_action_authority_matrix`는 Global Level을 복제하지 않고 다음 cap을 결합한 파생 SSOT다.

`min(global, task capability, action capability, model capability, health cap, user cap, approved level)`

Lv3 이상 final 참여에는 모델과 호환되는 명시적 사용자 grant가 필요하다. UI와 Provider는 Level을 자체 계산하지 않고 Authority Resolver 결과만 사용한다.

## Authority Grant

Grant는 `aits_local_engine_authority_grant.v1` 계약으로 기록한다. proposed 상태는 권한이 아니며, 명시적 사용자 승인과 완전한 model/task/action identity가 있어야 approved가 된다. 모델 또는 calibrator가 바뀌어 호환되지 않으면 재승인이 필요하다. 자동 grant와 UI 직접 JSON 쓰기는 금지한다.

## Resolver와 안전

Resolver는 action, confidence, risk, abstention, OOD, health, drift, model/calibrator, resource gate, user grant를 함께 평가한다. Resolver는 metadata만 반환하며 action을 변경하거나 주문을 생성하지 않는다.

LOCAL final 후보가 미래에 허용되더라도 OrderIntent 생성, OrderAdapter 호출, Upbit 호출, Guard override는 LOCAL 계층에서 수행하지 않는다. 주문성 행동은 반드시 기존 Validator → RiskGuard → LivePreflight → Execution → Reconciliation 경로를 거친다.

## Teacher audit

Lv4/Lv5에서도 외부 AI를 끄지 않는다. 위험, 낮은 신뢰도, OOD, drift, 모델 변경 직후와 정기 표본에 대해 감사 요청을 생성한다. 실제 호출은 `strategy.ai_provider`와 CostGuard 정책을 따른다.

## Resource gate

승격 가능한 모델은 CPU-only, 경량 artifact, 허용 latency/memory, package/schema compatible이어야 한다. GPU 또는 Ollama 같은 외부 runtime이 필수인 모델은 차단한다. threshold는 Authority Policy SSOT에 있다.

## 현재 운영 상태

- Global/Effective Level: 1
- Authority: `candidate_only`
- LOCAL final action: 0
- 자동 promotion/grant: 0
- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `safe_for_live_expansion=false`
- Ollama developer-only, live auto-generate disabled

이번 구조 Sprint에서는 앱 ON, 실제 주문, runtime acceptance를 수행하지 않는다.
