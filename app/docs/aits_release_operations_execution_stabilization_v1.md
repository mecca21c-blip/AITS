# AITS Release Operations Execution Stabilization V1

## 목적

Master Acceptance에서 차단된 Essential Backup, 설치 데이터 migration, 지원용 진단 번들의 실제 파일 작업 경로를 안전하게 제공한다. 이 계층은 거래 판단이나 주문 계층과 무관하며 앱이 OFF인 상태에서만 동작한다.

## 공통 승인 계약

모든 실제 작업은 `aits_release_operation_context.v1`을 사용한다. 명시적 사용자 승인, runtime OFF 확인, 실행 권한, 읽을 source, 분리된 target과 staging, operation lock을 모두 검증한다. dry-read와 observe-only 컨텍스트는 파일을 생성하거나 이동할 수 없다.

## Essential Backup

`essential` profile은 Authority, Capability, Health, Continuous Learning, Teacher Sync, 모델·calibrator 포인터, Intent, Effective Policy, 정책 제안 상태와 schema/release provenance를 ZIP으로 보존한다. API key, `.env`, credential, raw prompt, 전체 log와 cache는 제외한다. 임시 ZIP 생성 후 내부 hash, JSON/JSONL, secret scan과 read-back을 통과한 경우에만 최종 이름으로 전환한다.

## Migration

Migration은 source catalog와 필수 backup을 만든 뒤 staging에 허용된 데이터를 복사한다. checksum, structured data, Authority, Champion, Policy와 Intent 보존을 확인한 후에만 target을 atomic하게 활성화한다. source는 삭제하거나 다시 쓰지 않는다. 활성화 결과에는 이전 target checkpoint가 포함되며 동일 승인 컨텍스트로 실제 rollback을 검증할 수 있다.

## 지원용 진단 번들

지원 번들은 version/build, 안전한 설정 요약, provider 연결 여부, Authority/Health, 모델 ID, Policy/Intent 식별 정보, hardware/catalog/schema, acceptance·defect 요약과 정제된 최근 log만 포함한다. 계정 원문, holdings/balance, API key, Authorization, raw prompt, 전체 학습·outcome source는 포함하지 않는다. ZIP을 다시 열어 manifest와 모든 payload hash 및 secret pattern을 검증한다.

## 격리 Acceptance

`tools/release/test_release_operations.py`는 현재 실제 state/catalog 파일의 비밀정보 제외 read-only 사본을 OS temp에 만든다. 그 사본에서 backup과 support ZIP을 실제 생성하고 migration staging, activation, resolver 전환, rollback을 수행한다. 완료 전후 `C:\AITS\data`와 `%LOCALAPPDATA%\AITS`의 content digest를 비교한다. 실제 사용자 root의 migration activation은 수행하지 않는다.

## Master Acceptance 재개

기존 캠페인과 defect 원본은 보존한다. 격리 검증을 통과한 결함에는 append-only transition을 추가하며 상태는 `acceptance_retest_required`로 둔다. RC2에서 Artifact provenance, packaged first-run, App/Data root, backup, migration, support bundle을 다시 확인한 뒤 Explicit Live Approval Gate부터 기존 캠페인을 계속한다. Acceptance 재검증 전에는 결함을 closed로 처리하지 않는다.

## 안전 경계

- 앱 ON과 packaged executable 실행 금지
- 실제 사용자 data root activation 금지
- 주문, Router, RiskGuard, LivePreflight, Execution 변경 금지
- Authority, Level, Champion, Policy, Intent 변경 금지
- 원본 삭제와 secret/raw prompt bundle 금지
