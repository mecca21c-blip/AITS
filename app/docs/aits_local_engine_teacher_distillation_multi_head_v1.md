# AITS LOCAL_ENGINE Teacher Distillation and Multi-Head Core V1

## 1. Sprint 요약

이 Sprint는 기존 `wait` mode baseline을 teacher-distilled multi-action candidate engine으로 교체하는 구조를 추가한다. 입력은 실제 candidate observation과 exact-joined outcome/provider metadata뿐이며 fuzzy join, synthetic label, duplicate oversampling을 사용하지 않는다.

LOCAL_ENGINE은 계속 candidate-only다. 이 Sprint는 Router, RiskGuard, LivePreflight, Execution, Order 계층을 변경하지 않으며 live 판단 권한을 부여하지 않는다.

## 2. Teacher distillation dataset

Derived outputs:

- `data/ai_decision_training/local_engine_teacher_distillation_records.jsonl`
- `data/ai_decision_training/local_engine_teacher_distillation_excluded.jsonl`
- `data/ai_decision_training/local_engine_teacher_distillation_summary.json`

Teacher action 우선순위는 명시적 `external_decision.action`, OpenAI/Gemini `final_decision.action` 순서다. `local_safety_hold`는 teacher action으로 취급하지 않는다. Teacher가 없으면 action label은 null이며 다음 표준 reason을 기록한다.

- `provider_request_cooldown`
- `provider_key_missing`
- `provider_unavailable`
- `network_unavailable`
- `cost_guard_blocked`
- `external_not_required`
- `historical_metadata_missing`

Action 학습에는 `teacher_present=true` 레코드만 사용한다. Teacher가 없는 레코드는 provenance와 향후 abstention/risk 학습을 위해 보존한다.

## 3. Label leakage 방지

모델 encoder는 outcome label, checkpoint price/PnL, final action, teacher action을 feature로 읽지 않는다. 입력은 decision 시점에 저장된 `feature_context`뿐이다. `feature_context.provider`의 agreement/escalation 값도 외부 응답 이후 생성될 수 있어 명시적으로 제외한다.

Split은 시간 순서와 `decision_id` group을 함께 사용한다. 동일 decision의 checkpoint가 train/validation/holdout에 나뉘지 않는다. Class imbalance는 sample weight로 처리하며 레코드 복제나 인위적인 비대기 표본은 없다.

## 4. Task별 feature contract

- Position: position, market, indicators, risk, portfolio exposure, data quality
- Portfolio: portfolio totals/cash/exposure/cap/position count, risk budget, data quality
- Candidate/rotation: opportunity, market, portfolio cap/cash, risk, data quality

Runtime adapter는 `risk`와 `sell_unit_guard`를 factual alias로 처리한다. Portfolio context가 존재해도 teacher sample이 부족하면 position head로 강제 추론하지 않고 `multi_head_task_unsupported:portfolio_management_decision`으로 abstain한다.

## 5. Multi-action head

구현은 NumPy 기반 class-weighted multinomial logistic head다. 현재 실제 teacher label이 있는 action만 지원한다.

- Supported: `hold`, `sell`, `take_profit`, `wait`
- Insufficient/unsupported: `buy`, `add`, `reduce`, `stop_loss`, `rotate`

Artifact에는 feature scaler, action probabilities, class distribution, per-action metrics가 포함된다. 학습 표본이 없는 action은 지원 완료로 표시하지 않는다.

## 6. Confidence and abstention

Confidence는 top action probability, top1-top2 margin, empirical validation bucket, payload quality를 사용한다. Empirical bucket shrinkage가 가능한 경우 calibrated confidence를 생성하며 그렇지 않으면 uncalibrated probability 상태를 명시한다.

낮은 confidence, 작은 action margin, blocked risk에서는 `abstain_required=true`와 구조화된 reason을 기록한다. Abstention은 BASIC fixed action이나 live action을 강제하지 않는다.

## 7. Risk and escalation

Risk head는 valuation mismatch, stale market data, position weight, cap remaining, volatility, missing features, feature quality 및 action uncertainty를 사용한다.

출력은 `low/medium/high/blocked`, score, factors, blockers, order suitability다. `riskguard_required=true`와 `livepreflight_required=true`는 항상 유지된다.

Escalation head는 uncertainty, order-capable action, medium 이상 risk, abstention을 근거로 external confirmation을 추천한다. CostGuard 우회는 허용하지 않는다.

## 8. ETA and invalidation

ETA head는 teacher ETA가 있으면 우선 사용하고, 없으면 동일 task/scope의 실제 redecision cadence를 bucket으로 학습한다. 고위험 및 order-capable candidate는 명시된 monitoring policy override를 사용한다.

Invalidation은 실제 feature threshold만 사용한다. 현재 MA20이 존재하면 factual price-cross condition을, market stale 상태가 관측 가능하면 stale transition condition을 생성한다. Threshold 근거가 없으면 condition을 만들지 않고 missing reason을 기록한다.

## 9. Evidence reason composer

Composer는 존재하는 position PnL, momentum, volatility, cap remaining, MA 관계, risk factor만 한국어 문장에 사용한다. Raw prompt나 GPT 문장을 저장하지 않으며 evidence에 없는 feature를 언급하지 않는다.

## 10. Registry and runtime contract

Registry entry schema는 `aits_local_engine_multi_head_model.v2`이며 다음 별도 pointer를 유지한다.

- `latest_usable_multi_head_model_id`
- `latest_multi_head_training_attempt_id`

No-data attempt가 마지막 usable pointer를 덮어쓰지 않는다. Runtime loader는 multi-head bundle을 우선하되 기존 baseline bundle 호환성을 유지한다.

Candidate output에는 action probabilities, margin, raw/calibrated confidence, risk, escalation, ETA, invalidation, evidence reason이 포함된다. Observation에는 structured teacher provenance도 기록한다.

안전 필드:

- `candidate_only=true`
- `applied_to_final_action=false`
- `final_action_unchanged=true`
- `safe_for_live_decision=false`
- `live_decision_enabled=false`
- `safe_for_live_expansion=false`
- `fake_prediction=false`

## 11. Evaluation snapshot

2026-07-16 14:19 KST ephemeral evaluation 기준:

- Teacher present/absent: 213 / 7
- Label distribution: hold 109, wait 71, take_profit 25, sell 8
- Time/group split: train 148, validation 33, holdout 32
- Validation predicted actions: hold 20, wait 5, take_profit 8
- Non-wait prediction ratio: 84.85%
- Macro F1: 0.3801
- Balanced accuracy: 0.5550
- Wait baseline accuracy: 0.3333
- Confidence unique: 26, fixed=false
- Risk: low 25, medium 8
- ETA: 60 seconds 25, 180 seconds 8
- Invalidation nonempty: 33/33
- Reason nonempty/evidence valid: 33/33

Sell validation support는 2건이며 recall 0이다. Multi-action 구조는 wait-only를 벗어났지만 sell 및 take-profit metric은 아직 작은 표본 때문에 신뢰할 수 없다.

## 12. Portfolio blocker

Portfolio historical decision은 존재하지만 exact-joined portfolio teacher candidate가 0건이다. Fake label이나 position-head fallback은 금지되므로 portfolio head는 `portfolio_head_missing`으로 남는다. 다음 필요한 데이터는 실제 portfolio context와 external teacher action이 함께 기록된 exact-joined candidate observation이다.

## 13. 권한 및 운영 상태

- LOCAL final action 사용: 0
- Applied-to-final mutation: 0
- Actual order/Managed Pool mutation: 없음
- RiskGuard/LivePreflight/Execution 경계: 변경 없음
- Ollama: developer-only
- Ollama live auto-generate: false

현재 multi-head artifact는 shadow/candidate evaluation 전용이다.
