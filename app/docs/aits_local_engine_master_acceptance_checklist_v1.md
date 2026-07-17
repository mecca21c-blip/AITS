# AITS LOCAL_ENGINE Master Acceptance Checklist v1

## 실행 원칙

이 체크리스트는 전체 AITS 구조가 완성된 뒤 단 한 번의 통합 runtime acceptance에 사용한다. 현재 권한이 Lv1이면 Lv3~Lv5는 활성 판단이 아니라 dormant contract와 권한 차단이 정상인지 검사한다. 실제 주문은 별도 승인된 범위와 기존 안전 계층 안에서만 관찰한다.

## 1. 앱과 자원

- [ ] App startup과 ON/OFF lifecycle이 정상이다.
- [ ] hard freeze가 없고 heartbeat가 지속된다.
- [ ] 저사양 노트북 모드에서 CPU/memory/UI queue가 허용 범위다.
- [ ] LOCAL artifact가 CPU-only, package/schema compatible이다.
- [ ] 외부 runtime 또는 Ollama가 배포 필수 dependency가 아니다.

## 2. 데이터 SSOT

- [ ] Holdings SSOT와 화면이 일치한다.
- [ ] Managed Pool과 Holdings가 일치한다.
- [ ] SellEvaluation의 수량·평가액 단위가 일치한다.
- [ ] Market/Indicator/Portfolio payload freshness와 품질 grade가 유효하다.
- [ ] source decision/outcome/teacher/candidate record가 보존된다.

## 3. Provider와 LOCAL 판단

- [ ] `strategy.ai_provider`가 Provider SSOT다.
- [ ] GPT/Gemini teacher 응답과 absent reason provenance가 정확하다.
- [ ] LOCAL candidate multi-head contract가 생성된다.
- [ ] Confidence/Risk/Abstention/ETA/Invalidation/Reason이 분화된다.
- [ ] Level 2 Co-Pilot metadata와 external final 요구가 유지된다.
- [ ] Lv3에서 승인된 비주문 action만 LOCAL final 후보가 가능하다.
- [ ] Lv3 주문성 action은 외부 확인 없이는 안전 보류된다.
- [ ] Lv4는 승인 task/action pair에서만 local final candidate가 가능하다.
- [ ] Lv5는 승인 범위만 local-first이며 audit/escalation이 유지된다.
- [ ] 현재 Lv1이면 Lv3~Lv5 local final source가 0이다.

## 4. 권한과 모델

- [ ] Global Authority, Task Capability, Task-Action Matrix가 일치한다.
- [ ] 사용자 grant 없이 Lv3 이상 권한이 0이다.
- [ ] Grant model/calibrator compatibility가 검증된다.
- [ ] Champion/Challenger 교체와 Level/Task grant가 분리된다.
- [ ] Health/Drift/Confidence cap이 하향으로 작동한다.
- [ ] automatic demotion과 rollback이 준비되어 있다.
- [ ] automatic promotion과 automatic grant가 0이다.
- [ ] 사용자 promotion 승인/보류 이력이 남는다.

## 5. Review와 학습

- [ ] AI Review pending/partial/final lifecycle이 exact join으로 갱신된다.
- [ ] 판단 품질과 결과 품질이 분리된다.
- [ ] Learning Journal과 반복 패턴이 학습 우선순위에만 반영된다.
- [ ] Policy suggestion이 자동 적용되지 않는다.
- [ ] Teacher Sync가 필요 조건에서 요청된다.
- [ ] live ON 중 heavy learning이 0이다.
- [ ] OFF maintenance가 curation → feature → distillation → training → calibration → evaluation을 완주한다.
- [ ] failed/no-data attempt가 usable Champion/calibrator pointer를 덮어쓰지 않는다.

## 6. 주문 안전 경로

- [ ] LOCAL은 OrderIntent, OrderAdapter, Upbit API를 직접 호출하지 않는다.
- [ ] Validator가 모든 future local final candidate에 필수다.
- [ ] RiskGuard와 LivePreflight가 필수다.
- [ ] SellUnitGuard와 CostGuard가 유지된다.
- [ ] 기존 Execution submit path가 변경되지 않았다.
- [ ] 주문 발생 시 audit, reconciliation, remaining-position replanning이 완료된다.
- [ ] missed submit이 0이다.
- [ ] Managed Pool mutation은 기존 정책 경로에서만 발생한다.

## 7. Outcome과 상태 무결성

- [ ] 5m/15m/1h outcome과 opportunity cost가 exact identity로 연결된다.
- [ ] candidate/teacher/final/order/reconciliation provenance가 보존된다.
- [ ] state/grant/matrix/model/calibration 파일이 유효하다.
- [ ] corrupt derived data quarantine와 재생성이 가능하다.
- [ ] dry-read/observe-only 전후 source와 Authority/Champion hash가 불변이다.

## 8. UI

- [ ] 현재 Level, 역할, Health, 최종 판단 미적용 여부가 일치한다.
- [ ] Task별 권한과 외부 AI 필요 여부가 사용자 언어로 표시된다.
- [ ] 모델 교체, Level 승격, Task grant, rollback이 별개 작업으로 설명된다.
- [ ] 승인 후보가 없으면 승인 버튼이 숨겨진다.
- [ ] raw secret/prompt/snake_case가 노출되지 않는다.
- [ ] hidden tab throttle과 low-resource mode가 유지된다.

## 9. Packaging/resource compatibility

- [ ] 패키지 환경에서 model/calibrator artifact를 읽을 수 있다.
- [ ] artifact size, latency, peak memory가 Authority Policy 한도 내다.
- [ ] Ollama live generate가 0이며 developer-only다.
- [ ] Packaging 산출물에는 runtime data와 secret이 포함되지 않는다.

## 완료 판정

`aits-master-integrated-runtime-acceptance-v1-summary --observe-only`는 이 계약의 증거를 집계한다. 실제 통합 실행 전에는 `final_runtime_test_executed=false`가 정상이다. 최종 PASS에는 권한별 활성/차단 증거, 안전 계층 무변경, 주문 provenance, source 보존, UI 일치가 모두 필요하다.
