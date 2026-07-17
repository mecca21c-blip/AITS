# AITS Windows Packaging and Release Operations V1

## Release profile

- Primary: Windows x64 PyInstaller one-directory GUI (`AITS.exe`, console 없음).
- Secondary: explicit `portable.flag`를 포함한 진단용 ZIP.
- Installer: Inno Setup source 제공. 빌드 도구가 존재할 때만 installer를 생성한다.
- Channel: `release_candidate`; version SSOT는 `app/version.py`다.
- Python, venv, Ollama, GGUF 또는 외부 LLM runtime 설치를 요구하지 않는다.

패키징된 실행 파일은 이 Sprint에서 실행하지 않는다.

## Path SSOT

`AITSPathResolver`가 APP_ROOT, PACKAGED_RESOURCE_ROOT, USER_DATA_ROOT, USER_CONFIG_ROOT, USER_BACKUP_ROOT, DEV_ROOT, PORTABLE_ROOT를 단독 결정한다. Installer 데이터는 `%LOCALAPPDATA%\AITS`, 기본 백업은 `%USERPROFILE%\Documents\AITS Backups`에 둔다. `AITS_HOME`, `AITS_DATA_ROOT`, `AITS_BACKUP_ROOT` override를 지원한다. 설치 폴더는 read-only이며 runtime data/log/model을 쓰지 않는다.

## Include and exclude

포함: application, PySide6/Qt plugins, 경량 LOCAL inference, NumPy/필요 dependency, CA bundle, UI asset, schema/migration contract, license/SBOM, release manifest.

제외: 사용자 data/model/Authority/Intent/Policy, logs/reports/backups/archive/cache, `.env`, secrets/credential, raw prompt, Git metadata, venv, Ollama binary/model, 대형 LLM artifact. Release model bundle은 승인된 model만 허용하며 현재 RC는 bootstrap model을 포함하지 않는다.

## First run and resources

Fresh install은 OFF, 자동 주문 없음, low-resource mode, background chart 제한, heavy learning OFF, Ollama developer-only로 시작한다. OMP/MKL/OpenBLAS/NumExpr thread limit와 Qt software rendering 기본값은 QApplication 전에 적용한다. Provider key 미설정은 정상이며 provider Preview/Save/Connection ownership은 기존 계약을 유지한다.

## Migration, update, rollback

기존 `C:\AITS`는 감지만 하며 자동 이동하지 않는다. Migration은 catalog→용량 확인→승인→Essential backup→staging copy→checksum/record/schema 검증→atomic activation→source 보존 순서다. Update도 manifest/hash/schema 검증, OFF, backup, app/data staging, validation, switch, rollback을 따른다. App rollback과 data rollback을 분리하고 uninstall은 사용자 데이터를 기본 보존한다.

## Secrets and support

기존 encrypted secret store를 유지한다. Sanitized export는 sensitive field를 제외한다. 선택적 backup encryption backend가 없으므로 UI에서 암호화를 지원한다고 표시하지 않으며 plaintext fallback도 허용하지 않는다. Support bundle은 사용자 명시 생성만 가능하고 key/account/raw prompt/full training source를 제외한다.

## Artifacts and verification

`tools/release/build_release.py --profile release_candidate --clean --no-run`이 one-dir와 portable ZIP을 생성한다. `verify_release.py`는 executable, manifest hash, Qt plugin, dependency/license, schema compatibility, secret/runtime/user-model/Ollama 제외를 정적으로 검사한다. build output은 commit하지 않는다.

## Safety invariants

LOCAL Lv1/candidate_only, Champion/Authority/Intent/Policy, Provider final authority, RiskGuard, LivePreflight, Execution, Managed Pool은 불변이다. 패키징은 앱 ON, 주문, migration apply, restore 또는 runtime acceptance를 수행하지 않는다.
