# AITS LOCAL_ENGINE Task Coverage / Portfolio / Non-wait Learning V1

## 목적

이 계약은 모든 적격 AI provider decision에서 LOCAL_ENGINE candidate 시도 여부를 관찰하고, Position·Portfolio·non-wait teacher 데이터를 exact provenance로 offline 학습에 연결한다. LOCAL_ENGINE은 계속 candidate-only이며 final action, 주문, Managed Pool을 변경하지 않는다.

## Candidate coverage

`data/local_engine/local_engine_task_coverage.jsonl`은 provider decision마다 다음 사실을 기록한다.

- source task와 canonical model task
- candidate eligibility, attempt, availability, observation persistence
- feature/model blocker와 supported task/action
- teacher/final provider provenance
- prediction/outcome linkage

`ai_redecision`은 scope에 따라 Position 또는 Portfolio model task로만 canonicalize한다. 원래 task는 `source_task`로 보존한다. 동일 coverage identity는 중복 append하지 않는다.

## Portfolio provenance와 head

Distillation은 candidate exact join을 우선 유지한다. Candidate가 없던 과거 record는 outcome 자체에 stable `decision_id`, 명시적 OpenAI/Gemini action, pre-decision `feature_context`가 모두 있을 때만 `outcome_decision_id` 방식으로 사용한다. 첫 checkpoint record만 선택하므로 checkpoint 이후 값은 feature가 되지 않는다.

Portfolio task는 Position feature gate를 사용하지 않는다. 실제 teacher sample이 충분한 offline Challenger만 Portfolio task support를 선언한다. Global Champion이 Portfolio를 지원하지 않을 때는 task를 지원하는 최신 usable Challenger를 candidate-only 관찰에 사용할 수 있으나 registry pointer와 authority는 변경하지 않는다.

## Non-wait 정책

buy/add/sell/reduce/take_profit/stop_loss/rotate는 실제 external teacher action만 label로 인정한다. 표본 없는 action은 지원 완료로 표시하지 않는다. 강제 주문, synthetic sample, duplicate oversampling, fuzzy join은 금지한다.

## 안전 경계

- `candidate_only=true`
- `applied_to_final_action=false`
- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `safe_for_live_expansion=false`
- RiskGuard, LivePreflight, Router, Execution 경계 유지
- Champion 자동 교체 및 Level 자동 승격 금지
- live ON 중 heavy learning 금지

## 검증

`local-engine-task-coverage-portfolio-nonwait-learning-v1-summary --observe-only`는 task별 coverage, Portfolio exact teacher recovery, non-wait 분포, offline training 상태, capability/authority, 금지 계층 상태를 함께 보고한다. 실제 coverage 완료 판정은 새 live decision이 coverage JSONL에 기록된 뒤에만 가능하다.
