# AITS Data Governance, Retention, Backup, Recovery V1

## 목적

이 구조는 AITS의 장기 운용 데이터에 대해 분류, 보관, 압축, 학습 활용, 백업 및 복구 계약을 제공한다. 이번 Sprint는 구조만 완성하며 원본 이동·삭제, 백업 bundle 생성, restore 적용, migration 적용을 실행하지 않는다.

## 단일 정책

`AppSettings.data_governance_policy`가 유일한 정책 SSOT다. 안전 기본값은 다음과 같다.

- 원본 자동 삭제: 꺼짐
- 파생 데이터 자동 정리: 꺼짐
- Critical State와 Champion 보호
- archive/backup/restore/migration: OFF 상태 + 명시 요청 + 사용자 승인
- secret/raw prompt: 일반 백업 제외

UI, archive, backup, retention 서비스는 별도 threshold를 만들지 않고 이 section을 소비한다.

## 데이터 분류

- Immutable Source: decision, candidate, outcome, teacher provenance, Intent/권한 이력. 재작성·자동 삭제 금지, 검증 후 archive 가능.
- Critical State: Authority, Capability, Health, model registry, active Intent. active 유지, atomic backup/migration 대상.
- Derived Learning: curation, feature, distillation, calibration, Review, Journal summary. source 존재 확인 후 OFF/manual 재생성 가능.
- Model Artifact: Champion, previous Champion, active Challenger와 호환 manifest. 참조·grant 검사 없이 정리 금지.
- Operational Log/Report: 기간·용량 정책 적용 가능. 중요 실패와 pinned incident 보호.
- Secret Excluded: API key, credential, `.env`, `secret.bin`, `secrets.json`, raw prompt. 내용·checksum을 UI/Catalog에 노출하지 않는다.

## Hot / Warm / Cold

Hot은 active append 파일, Warm은 manifest가 있는 `segment_*.jsonl.gz`, Cold는 runtime이 자동으로 읽지 않는 검증된 backup bundle이다. `AITSDataSourceResolver`는 active와 archive를 exact identity로 읽고 fuzzy merge를 하지 않는다. archive가 검증되기 전에는 active source를 정리하지 않는다.

## Archive와 Compaction

`AITSDataArchiveManager.plan()`은 read-only snapshot, 임시 gzip, record count/checksum 검증, manifest, atomic rename 순서를 명시한다. source cleanup은 별도 승인 작업이며 기본적으로 허용되지 않는다. 일/주/월 요약은 factual count와 source digest만 생성하며 원본을 대체하지 않는다.

## 학습 사용

학습 포함/제외는 source record를 수정하지 않는다. dataset/date/task/action/reliability 정책을 read-time resolver에 적용한다. archive 포함과 historical replay는 독립 설정이며 실패·위험 사례를 자동 제외하지 않는다.

## Backup

- Essential: 설정, 정책, Authority/Capability/Health, registry/grants, active Intent, 승인 상태.
- Learning: Essential + source/learning derived/calibration/선택 모델.
- Full: Learning + model/archive manifest/선택 운영 이력.

모든 profile은 plan → secret exclusion → temp ZIP → hash/count 검증 → atomic rename → audit 순서를 따른다. 이번 Sprint에서는 plan만 검증한다.

## Restore와 Migration

Restore는 manifest/unsafe path/schema 검사 후 staging에 해제하고 checksum/count를 검증한다. 현재 상태 snapshot과 사용자 최종 승인 후에만 OFF 상태에서 atomic apply하며 실패 시 rollback한다. Migration도 source backup, staging 변환, count/hash 검증, 승인, atomic apply, rollback 계약을 사용한다. 현재 데이터에 강제 적용하지 않는다.

## 무결성과 Disk Pressure

무결성 검사는 JSON/JSONL, NUL, partial last line, schema/checksum/reference 문제를 분류한다. Derived 손상은 격리·재생성할 수 있지만 Source 손상은 자동 수정하지 않는다. Disk critical 상태도 source, Champion, Authority, order/reconciliation 기록을 자동 삭제하지 않으며 비핵심 heavy generation을 보류하고 backup/archive plan을 권고한다.

## UI 및 작업 경계

`AI 정책센터 → LOCAL_ENGINE 성장·운영 → 상세 관리 → 데이터·백업`에서 사용자 요약, Catalog, 보관 정책과 plan 작업을 제공한다. 기본 refresh는 metadata만 읽고 JSONL full scan은 worker/manual deep scan에서만 수행한다. heavy 작업은 OFF-only, 중복 실행 guard, progress/cancel 가능한 worker 계약을 따른다.

## 안전 불변식

- LOCAL Lv1 / `candidate_only` 유지
- LOCAL final source 0
- Provider/Effective Policy/Intent runtime 동작 불변
- RiskGuard/LivePreflight/Execution/OrderAdapter 불변
- 원본 자동 삭제·재작성 없음
- 실제 archive/backup/restore/migration 없음
- 실제 주문 및 Managed Pool mutation 없음

## 검증

`aits-data-governance-retention-backup-recovery-v1-summary --observe-only`는 protected hash 전후, 정책 SSOT, Catalog 분류, resolver, plan 계약, secret 제외, integrity/migration/disk/UI와 실행 0을 확인한다.
