# AITS LOCAL_ENGINE Continuous Learning / Level Authority v1

## 목적

GPT/Gemini 교사 데이터와 실제 outcome으로 성장하는 LOCAL_ENGINE의 운영 경계를 정의한다. 모델 학습과 운용 권한은 분리한다. 새 모델 생성, 높은 단일 지표, 데이터 누적만으로 권한이 올라가지 않는다.

현재 migration 상태는 **Level 1 / candidate_only**다. 기존 candidate observation 안전 계약과 `safe_for_live_decision=false`, `live_decision_enabled=false`, `safe_for_live_expansion=false`, `applied_to_final_action=false`를 유지한다.

## Level 계약

- Level 0: External Only. 유효한 LOCAL 모델이 없다.
- Level 1: Candidate. LOCAL은 후보만 기록하고 external provider가 final을 정한다.
- Level 2: Co-Pilot. routing/escalation을 보조하지만 external final을 유지한다.
- Level 3: Task Primary. 사용자가 승인한 비주문 task만 LOCAL final 후보가 된다.
- Level 4: Local Primary. 승인된 task/action pair에 한정하며 주문성 action은 RiskGuard와 LivePreflight가 필수다.
- Level 5: Internal Asset Manager. 지원 task의 기본 판단자지만 외부 교사 escalation과 모든 안전 계층을 유지한다.

실제 권한은 `min(global level, task capability, model capability, health cap, user cap)`이다. 승격은 평가 근거와 사용자 승인이 모두 있어야 한다. 강등과 롤백은 안전 방향이므로 자동 또는 사용자 요청으로 즉시 가능하다.

## 단일 SSOT와 영속성

운용 권한 SSOT는 `data/local_engine/local_engine_authority_state.json`이다. capability, health, learning, teacher sync 파일은 파생 진단이며 독립적인 Level 소유자가 아니다.

- JSON state는 임시 파일 기록, flush/fsync, 검증 후 atomic replace를 사용한다.
- history는 append-only JSONL이며 flush/fsync한다.
- NUL/손상 state는 quarantine 후 기존 candidate 권한에서 보수적으로 재구성한다.
- outcome/candidate 원본은 수정하지 않는다.
- observe-only/dry-read summary는 state/history를 쓰지 않는다.

## Capability와 Health

Capability Matrix는 position wait/hold, buy/add, sell/reduce, take-profit/stop-loss, portfolio, rotation, promotion candidate, risk, ETA, invalidation, reason을 독립 평가한다. 표본이 없거나 action recall이 부족한 task는 Level 0/1과 명시 blocker를 유지한다.

Health는 stable, watch, degraded, relearning, blocked를 사용한다. Health는 권한을 높일 수 없고 cap 또는 강등만 수행한다. drift monitor는 최근/과거 action 분포, confidence 변화, teacher disagreement를 경량 통계로 비교한다. outcome/regime 근거가 없으면 값을 만들지 않고 unavailable로 남긴다.

## Continuous Learning

Live ON 중 허용되는 작업은 candidate/teacher/outcome append, 경량 counter, training pending 기록뿐이다. curation, feature regeneration, training, calibration scan, challenger evaluation은 runtime OFF이면서 사용자가 명시한 maintenance에서만 실행한다.

Challenger는 최근 데이터 0.7, historical replay 0.3 원칙으로 평가한다. 최근 적응 개선과 과거 안전성 보존이 함께 확인돼야 promotion candidate가 된다. failed/no-data run은 latest usable Champion을 덮어쓰지 않는다.

## Teacher Sync와 Provider Router

Teacher Provider SSOT는 기존 `strategy.ai_provider`다. 별도 provider 설정을 만들지 않는다. degraded/강등 시 교사 연결과 최근 데이터 수집을 권고하지만 CostGuard를 우회하지 않는다.

Provider 경로는 Authority Manager metadata를 읽되 migration에서는 effective Level 1로 cap된다. `local_final_allowed=false`, external confirmation required를 유지한다. `_render_ai_engine_state`의 Preview 소유권은 변경하지 않는다.

## UI와 사용자 작업

기존 LOCAL 영역은 Level, health, authority, Champion/Challenger, 학습/teacher sync 상태, task별 Level·지원 action·표본, 유지/변경 이유를 한국어로 표시한다. 사용자는 Level 하향, authority 일시 중지, teacher sync 안내, 재학습 요청, 검증된 승격 승인, rollback을 요청할 수 있다.

수동 상향은 평가 blocker가 하나라도 있으면 적용하지 않는다. 재학습 요청은 pending만 기록하며 UI thread나 live runtime에서 heavy learning을 시작하지 않는다.

## 안전 불변식

- LOCAL_ENGINE은 현재 final action에 사용되지 않는다.
- RiskGuard, LivePreflight, DecisionRouter action logic, Execution/Order 계층은 변경하지 않는다.
- Ollama는 developer-only이며 live auto-generate는 비활성이다.
- fake level, promotion, demotion, training data, metric을 만들지 않는다.
- 실제 주문과 Managed Pool mutation을 수행하지 않는다.

검증 mode는 `local-engine-continuous-learning-level-authority-v1-summary --observe-only`다.
