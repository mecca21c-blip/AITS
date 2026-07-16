# AITS LOCAL_ENGINE Performance Report V1

## 1. 요약

이 문서는 `local-engine-performance-report-v1-summary --observe-only`가 2026-07-16 13:21 KST에 계산한 ephemeral snapshot을 설명한다. 원본 candidate/outcome 파일과 persisted calibration profile은 수정하지 않았다.

현재 LOCAL_ENGINE은 안전한 candidate-only 배관과 outcome join은 갖췄지만, 성능 측면에서는 `wait` 단일 action baseline에 가깝다. final action exact match는 32.06%, 외부 teacher(OpenAI) exact match는 29.70%다. confidence는 209건 중 208건이 동일값에 집중됐고 전부 미보정 상태이므로 유효한 confidence 학습 신호로 판단하지 않는다.

## 2. 데이터 규모

- Candidate observations: 209
- Valid candidates: 209
- Corrupt / unsafe contract: 0 / 0
- Joined checkpoints: 564
- Unique joined decisions: 207
- Usable ephemeral calibration decisions: 207
- Candidate가 없어 fuzzy join 없이 제외된 decisions: 341

레코드 수는 외부 runtime append에 따라 이후 summary 실행 시 증가할 수 있다. 성능 계산은 persisted profile이 아니라 최신 ephemeral exact join을 사용한다.

## 3. LOCAL vs final/teacher 비교

- LOCAL vs final exact match: 67/209, 32.06%
- LOCAL vs teacher exact match: 60/202, 29.70%
- LOCAL vs OpenAI exact match: 60/202, 29.70%
- `local_safety_hold` bucket: 7/7, 100%

Candidate schema에는 별도 `teacher_action`이 없다. 따라서 teacher가 존재하는 레코드에서는 당시 기록된 `final_action`을 teacher action proxy로 사용한다. 이는 명시적인 파생 규칙이며 teacher metadata를 보정하거나 생성하지 않는다.

Final action 분포는 `hold` 109, `wait` 67, `take_profit` 25, `sell` 8이다. LOCAL은 전부 `wait`이므로 `hold`를 exact match로 세지 않았다.

## 4. Action 분포

- LOCAL `wait`: 209/209, 100%
- Non-wait: 0%
- buy/sell/take_profit/rotate candidate: 없음

따라서 현재 일치율과 outcome score는 일반적인 multi-action 모델 성능이 아니라 wait-only baseline 성능으로 해석해야 한다.

## 5. Confidence 분석

- Unique confidence values: 2
- Min / max / average: 0.594213 / 0.777048 / 0.776169
- Dominant value: 0.7770478903409092, 208/209(99.52%)
- `confidence_calibrated=true`: 0
- Uncalibrated: 209

Raw confidence/outcome correlation은 약 0.0227이지만 한 건을 제외한 confidence가 동일하다. 분산과 표본 다양성이 부족하므로 리포트는 상관계수를 유효한 학습 신호로 공개하지 않고 `confidence_concentrated_correlation_not_reliable`로 차단한다.

## 6. Outcome 기반 분석

207개 usable decision에서 calibration outcome proxy 기준 action-correct는 184건(88.89%)이다. Outcome label은 `avoided_loss` 102, `good_wait` 72, `bad_take_profit` 17, `good_take_profit` 8, `early_sell` 6, `good_sell` 2다.

이 수치는 실제 주문 수익률이 아니다. 실제 주문은 없으며, 대부분 wait 판단 이후 checkpoint 가격 변화와 기존 outcome label/score를 사용한 관찰 proxy다. 또한 모든 LOCAL action이 wait이므로 non-wait action의 결과 품질이나 action 간 상대 성능은 평가할 수 없다. final과 동일/상이한 checkpoint는 각각 174/390건이지만, 상이 bucket 역시 대부분 `wait` 대 `hold/sell/take_profit` 비교다.

## 7. Scope/Task 및 metadata

- Scope: KRW-ENSO 204, KRW-BERA 5
- Scope exact match: KRW-ENSO 30.39%, KRW-BERA 100%(표본 5)
- Task: position_management_decision 200, ai_redecision 9
- Task exact match: position_management_decision 29.0%, ai_redecision 100%(표본 9)
- Teacher source: OpenAI 202, blank 7
- Blank 7건 중 CostGuard cooldown 5건, final source `local_safety_hold` 7건
- Portfolio prediction blocked unique decisions: 70

작은 KRW-BERA/ai_redecision bucket의 100%를 일반화하면 안 된다. Teacher 부재 원인을 명시적으로 분석하려면 향후 `teacher_absent_reason` metadata 보강을 권고하지만 이번 Sprint에서는 schema나 원본을 변경하지 않는다.

## 8. Risk / ETA / invalidation

- Risk: `low` 209/209
- Blocker: `local_model_live_disabled_by_registry` 209/209
- ETA: 300초 209/209
- Empty invalidation conditions: 209/209, 100%

Risk, ETA, invalidation도 분포가 없어 head 품질 비교가 불가능하다. 특히 invalidation은 전부 비어 있어 후속 개선이 필요하다.

## 9. 현재 한계와 다음 개선 우선순위

1. **F. non-wait candidate 확보를 위한 data collection**: action head를 평가하려면 wait 이외의 실제 candidate 관찰 데이터가 우선 필요하다.
2. **B. confidence calibration 개선**: confidence 집중을 해소하고 outcome에 대해 검증 가능한 분산과 calibration을 확보한다.

그 다음 후보는 C(invalidation/ETA head)와 D(teacher_absent_reason metadata)다. 현재 데이터만으로 action head의 buy/sell/rotate 성능을 학습 또는 검증했다고 주장할 수 없다.

## 10. 안전 경계

- `candidate_only=true` 계약 유지
- `applied_to_final_action` count: 0
- LOCAL final action used count: 0
- `safe_for_live_expansion=false`
- 실제 주문 및 Managed Pool mutation 없음
- Ollama developer-only 유지, live auto-generate 비활성

이 리포트는 read-only 성능 관찰 결과이며 LOCAL_ENGINE에 live 판단 권한을 부여하지 않는다.
