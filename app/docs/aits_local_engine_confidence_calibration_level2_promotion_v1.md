# AITS LOCAL_ENGINE Confidence Calibration / Level 2 Promotion V1

## 목적

이 구조는 실제 OpenAI/Gemini teacher action에 대한 LOCAL_ENGINE 다중 action 확률을 보정하고, 기존 Authority Policy를 변경하지 않은 채 Lv2 보조 판단자 승격 가능성을 평가한다. 보정 결과는 주문 action을 직접 만들거나 final action을 변경하지 않는다.

## Calibration target과 source

- Primary target은 `teacher_present=true`이고 exact identity로 연결된 teacher action이다.
- teacher가 없는 `local_safety_hold`, CostGuard cooldown record는 action calibration target에서 제외한다.
- AI 복기의 `review_learning_eligible`, reliability grade, stage weight를 exact decision/prediction join으로 확인한다.
- pending/inconclusive review, model training group, 중복 decision group은 제외한다.
- outcome이나 weak/poor review를 teacher action으로 변환하지 않는다.
- fuzzy join, synthetic label, future checkpoint feature는 사용하지 않는다.

## Split 계약

현재 Champion이 학습에 사용한 train group은 calibration에서 제외한다. 남은 teacher/review 적격 decision을 시간순으로 정렬하고 decision group을 보존한다.

1. 가장 최근의 충분한 실제 session을 untouched holdout으로 격리한다.
2. 이전 구간의 앞 70%를 calibration fit으로 사용한다.
3. 이전 구간의 뒤 30%를 method validation으로 사용한다.
4. method 선택이 끝난 뒤에만 untouched holdout을 한 번 평가한다.

동일 decision은 두 split에 들어가지 않는다. session holdout을 만들 수 없을 때만 시간순 마지막 구간을 holdout으로 사용하며 그 사실을 blocker/summary에 남긴다.

## 평가 방법

배포 의존성을 늘리지 않는 NumPy 기반 후보를 비교한다.

- identity probability
- multiclass temperature scaling
- class-aware Platt-style logit scale/bias
- 충분한 task에는 task-specific calibrator
- 표본이 부족한 task에는 global fallback

Validation에서는 Brier, ECE, log-loss 순으로 비교하고 action balanced accuracy가 악화되는 후보를 제외한다. Holdout 결과를 보고 method를 다시 고르지 않는다.

## 이번 실제 attempt 결과

- source: 119 teacher-present / review-learning-eligible decisions
- calibration fit: 67
- validation: 29
- untouched session holdout: 23
- 선택 방법: temperature scaling
- holdout Brier: 0.465286 → 0.624684
- holdout ECE: 0.269877 → 0.351409
- holdout log-loss: 0.766355 → 1.090785
- balanced accuracy: 0.521739 → 0.521739
- unsafe prediction: 0 → 0

Validation에서는 개선됐지만 untouched holdout에서는 confidence metric이 악화됐다. 따라서 이 calibrator는 `holdout_rejected`로 기록했으며 artifact/usable pointer/runtime에 적용하지 않았다. Authority Policy의 Brier 상한 0.35는 변경하지 않았다.

## Registry와 runtime

- 성공/실패 attempt는 model registry에 source model, split count, metric, blocker와 함께 기록한다.
- 실패/no-data attempt는 `latest_usable_calibrator_id`를 덮어쓰지 않는다.
- usable artifact만 exact source model/schema가 맞을 때 candidate inference에서 로드한다.
- runtime candidate는 raw/calibrated probability, method, reliability, abstention을 기록한다.
- calibration이 불안정하거나 unsupported action이면 기존 probability와 external confirmation 경로를 유지한다.

## Lv2 승격 정책

Global Lv2 eligibility는 Authority Manager의 기존 threshold만 사용한다. 보정 결과가 holdout에서 안전하지 않거나 Brier 상한을 넘으면 promotion candidate를 만들지 않는다.

Promotion candidate가 생성되더라도:

- 자동 승격하지 않는다.
- 사용자 승인 전 Global Level 1 / `candidate_only`를 유지한다.
- Lv2 승인 후에도 GPT/Gemini 또는 안전 보류가 final action을 결정한다.
- RiskGuard, LivePreflight, CostGuard, Execution path는 그대로 유지한다.

## 현재 결론

이번 attempt는 `brier_threshold_not_met`로 종료한다. Champion `local_multi_head_20260717_061453`, Global Level 1, `candidate_only`를 유지한다. 다음 attempt는 새로운 teacher/outcome session이 축적된 뒤 validation 선택 단계부터 새롭게 수행하며 현재 holdout 결과에 맞춘 재튜닝을 하지 않는다.
