# AITS Current Source Map

## 1. 프로젝트 실행 흐름

현재 실행 진입점은 `run.py`이다.

흐름:

```text
run.py
-> load_dotenv()
-> init_app_context()
-> init_aits()
-> AITSOrchestrator(...)
-> headless 또는 GUI 실행
```

핵심 확인 사항:

- `run.py:init_aits()`는 현재 `AITSOrchestrator(config={}, app_state=None, ...)`로 생성한다.
- `run.py:run_headless()`는 `app_context["orchestrator"]`를 사용해 `run_cycle()`을 1회 실행한다.
- `run.py:launch_ui()`는 `app.ui.main_window.main(root_dir, data_dir)`만 호출한다.
- `app/ui/main_window.py`는 `app.ui.app_gui.main()`으로 위임한다.
- `app/ui/app_gui.py`의 `MainWindow`는 `state`, `root_dir`, `data_dir`를 받지만 `app_context`는 받지 않는다.

현재 의미:

- headless와 GUI 모두 Orchestrator 생성은 `run.py:init_aits()` 기준이다.
- UI 설정 객체는 `MainWindow._settings`에 존재하지만, 현재 Orchestrator 생성 인자로 전달되지 않는다.

## 2. 주요 디렉터리 역할

| 디렉터리 | 역할 | 현재 메모 |
|---|---|---|
| `app/ui/` | PySide6 GUI, 공통설정, API key 입력, provider 선택, 실행 제어 UI | 핵심 파일은 `app_gui.py`; 백업/후보 파일이 다수 존재 |
| `app/services/` | Orchestrator, Decision Router, AI Provider, 주문 어댑터, 시장/포트폴리오/설명 서비스 | AITS 판단/검증/실행 연결의 중심 |
| `app/utils/` | 설정 schema, prefs 저장/로드, 로깅/숫자 포맷 유틸 | `settings_schema.py`, `prefs.py`가 설정 SSOT |
| `app/core/` | AITS runtime state, module pack state, event bus, auth state | dataclass/state 계층 |
| `app/auth/` | 로그인 dialog | `login_dialog.py` |
| `app/db/` | 거래 DB 저장 계층 | `trades_db.py` |
| `app/strategy/` | KMTS 호환 runner 상태 컨테이너 | `runner.py`는 `_LAST_SETTINGS`, `_RUNNING` 보관 |
| `app/repository/` | 현재 분석 시점에 tracked source 없음 | 디렉터리는 있으나 소스 파일 없음 |
| `app/runtime/` | 현재 분석 시점에 tracked source 없음 | 디렉터리는 있으나 소스 파일 없음 |
| `app/docs/` | AITS 기준 문서 | v2.6/v2.7 AI verification 문서 존재 |

## 3. 핵심 파일별 역할 표

| 파일 | 역할 | 현재 수정 여부 | 주의사항 |
|---|---|---|---|
| `run.py` | dotenv 로드, app_context 생성, Orchestrator 생성, headless/UI 분기 | 미수정 | 현재 settings를 Orchestrator에 넘기지 않는 끊긴 지점 |
| `app/ui/main_window.py` | legacy-compatible UI entry wrapper | 미수정 | `app_gui.main()`만 호출 |
| `app/ui/app_gui.py` | 메인 UI, 공통설정, provider 선택, key 입력/저장/로드 | 수정 중 | API key 값 로그 금지, UI 저장 후 Orchestrator hot refresh 미연결 |
| `app/utils/settings_schema.py` | AppSettings/StrategyConfig schema | 수정 중 | `ai_openai_api_key`, `ai_gemini_api_key` 필드 존재 |
| `app/utils/prefs.py` | prefs 초기화, load/save/patch merge | 미수정 | env `OPENAI_API_KEY`를 `strategy.ai_openai_api_key`로 보강하는 경로 존재 |
| `app/services/aits_orchestrator.py` | AITS cycle orchestration, Router/Provider/OrderAdapter 연결 | 수정 중 | settings 주입 준비는 되었으나 run.py가 아직 app_state를 None으로 넘김 |
| `app/services/decision_router.py` | Router v2.6/v2.7, AI Verification, Shadow stats, Micro apply, RouterSummary | 기존 수정 있음 | action/order 경로와 confidence 반영 조건 주의 |
| `app/services/ai_engine_provider.py` | Local/OpenAI/Gemini provider, readiness, live call, key resolver | 수정 중 | env 우선, settings/config fallback resolver 존재 |
| `app/services/order_adapter.py` | ExecutionBridge 결과를 주문 후보로 변환/차단/제출 | 미수정 | `mode=disabled` 안전 기준 유지 필요 |
| `app/services/order_service.py` | 주문 서비스 표면 | 미수정 | 실주문 경로 수정 금지 |
| `app/services/execution_bridge.py` | action plan -> BridgeResult | 미수정 | 승인/차단 action 흐름 수정 금지 |
| `app/services/ai_decision_service.py` | 1차 AI/basic decision 생성 | 미수정 | Router 이전 판단 생성 |
| `app/services/basic_decision_engine.py` | basic/rule 기반 fallback 판단 | 미수정 | 기존 rule 흐름 보존 |
| `app/services/portfolio_brain.py` | portfolio target 구성 | 미수정 | Orchestrator cycle 입력 |
| `app/services/regime_detector.py` | market regime 판단 | 미수정 | Orchestrator cycle 입력 |
| `app/services/module_pack_resolver.py` | module pack runtime 해석 | 미수정 | AI decision pack_runtime 입력 |
| `app/core/aits_state.py` | AITS runtime state dataclass | 미수정 | Orchestrator state 저장 |
| `app/core/module_pack_state.py` | module pack state 정의 | 미수정 | module pack resolver와 연결 |
| `app/strategy/runner.py` | UI runner 상태 컨테이너 | 미수정 | `start_strategy(settings)`가 settings를 보관하나 Orchestrator에는 직접 전달하지 않음 |
| `data/shadow_history.json` | shadow signal history | 데이터 | 코드 아님 |
| `data/shadow_performance.json` | shadow performance 누적 기록 | 데이터 | 검증/성과 산출물 |
| `data/logs/aits.log` | AITS runtime log | 산출물 | 커밋 제외 권장 |

## 4. AI Verification 흐름

현재 판단/검증 흐름:

```text
Market/Portfolio state
-> AIDecisionService.decide()
-> AITSOrchestrator._read_ai_provider_for_router()
-> DecisionRouter.route()
-> DecisionRouter._run_ai_verification_suggestion()
-> AIEngineProvider.verify_router_decision()
-> Local/OpenAI/Gemini verifier path
-> AIVerificationDetail / AIVerificationWeight
-> AIVerificationShadowDelta
-> RouterSummaryAI
-> passthrough decision
-> ExecutionBridge
-> AITSOrderAdapter(mode=disabled)
```

주요 로그:

- `[AITS][Orchestrator] router_ai_provider_injection`
- `[AITS][Orchestrator] ai_provider_key_injection`
- `[AITS][Orchestrator] verifier_pool_init`
- `[AITS][Orchestrator] verifier_select`
- `[AITS][AIVerification]`
- `[AITS][AIVerificationDetail]`
- `[AITS][AIVerificationShadowDelta]`
- `[AITS][AIVerificationWeight]`
- `[AITS][RouterSummaryAI]`
- `[AITS][AIShadowStats]`
- `[AITS][AIShadowPerformance]`
- `[AITS][AIMicroApply]`
- `[AITS][AIMicroFinalApply]`

현재 provider pool:

- local verifier는 기본 존재한다.
- OpenAI verifier는 `AITS_ENABLE_OPENAI_VERIFIER=1`일 때 생성된다.
- Gemini verifier는 `AITS_ENABLE_GEMINI_VERIFIER=1`일 때 생성된다.
- OpenAI/Gemini 실제 호출은 추가로 `AITS_AI_VERIFY_LIVE_ONCE=1`이 필요하다.

## 5. API Key 저장/사용 흐름

목표 흐름:

```text
공통설정 UI 입력
-> app_gui.py 저장 patch
-> prefs/settings 저장
-> run.py 또는 UI hot refresh가 Orchestrator에 settings 전달
-> AITSOrchestrator가 AIEngineProvider(strategy/settings/config)에 주입
-> AIEngineProvider._get_config_api_key()
-> OpenAI/Gemini live verifier call
```

현재 구현된 부분:

- OpenAI 입력창: `ed_openai_key`
- Gemini 입력창: `ed_gemini_key`
- provider 선택: `cb_ai_provider`, `_set_ai_provider_ui_active()`
- `openai`, `chatgpt` alias는 `gpt`로 정규화된다.
- `google`, `google_gemini` alias는 `gemini`로 정규화된다.
- OpenAI 저장: `strategy.ai_openai_api_key`
- Gemini 저장: `strategy.ai_gemini_api_key`
- schema: `StrategyConfig.ai_openai_api_key`, `StrategyConfig.ai_gemini_api_key`
- provider resolver: `AIEngineProvider._get_config_api_key(provider)`
- resolver 우선순위: env key first, settings/strategy/config fallback second.

현재 미완성 부분:

- `run.py:init_aits()`가 settings를 읽지 않고 `app_state=None`, `config={}`로 Orchestrator를 만든다.
- 따라서 `AITSOrchestrator.strategy`가 headless에서 `None`으로 남는다.
- UI에서 저장된 `self._settings.strategy`가 Orchestrator 인스턴스에 hot refresh되지 않는다.

## 6. 현재 끊긴 지점

현재 확인된 문제:

- `run.py:init_aits()`가 `AITSOrchestrator(config={}, app_state=None)`로 생성한다.
- UI settings의 `strategy.ai_openai_api_key`, `strategy.ai_gemini_api_key`가 Orchestrator까지 전달되지 않는다.
- 따라서 `AIEngineProvider._get_config_api_key()`의 settings fallback이 아직 실제 UI key를 받지 못한다.
- 최근 headless 로그에서도 `strategy_attached=False`, `openai_key_present=False`, `gemini_key_present=False`로 확인된다.

현재 구조상 provider 선택도 다음 조건이 필요하다:

- settings 또는 config에서 `strategy.ai_provider`가 Orchestrator로 전달되어야 한다.
- 또는 dryrun override env가 있어야 local이 아닌 provider로 route된다.
- OpenAI/Gemini verifier는 enable env가 있어야 pool에 생성된다.

## 7. 다음 패치 후보

1. 103차: `run.py:init_aits()`에서 `load_settings()` 결과를 Orchestrator에 전달
   - 예: `settings = load_settings()`
   - `AITSOrchestrator(config=settings.model_dump(), app_state=settings, ...)`
   - key 값 로그 금지.

2. 104차: UI 저장 후 Orchestrator settings/strategy hot refresh
   - `self._settings` 저장/재로드 완료 후 `_get_aits_orchestrator()`로 Orchestrator 조회
   - `orch.settings = self._settings`
   - `orch.app_state = self._settings`
   - `orch.strategy = self._settings.strategy`
   - verifier pool 재생성 또는 provider kwargs 갱신 필요 여부 확인.

3. 105차: 실제 Gemini/OpenAI UI key 기반 1회 호출 검증
   - test env off
   - provider non-local
   - verifier enable env on
   - `AITS_AI_VERIFY_LIVE_ONCE=1`
   - OrderAdapter disabled/submitted=0 확인.

## 8. 절대 건드리면 안 되는 파일/영역

다음 영역은 현재 안전 기준상 직접 수정 금지 또는 별도 승인 필요:

- `app/services/order_adapter.py`
- `app/services/order_service.py`
- `app/services/execution_bridge.py`
- 실주문 요청 경로
- `buy_order_request`
- `sell_order_request`
- `approved_actions` 생성 경로
- `execution_mode` / `live_trade` 경로
- OrderService 호출부
- action override 경로

## 9. 안전 기준

현재 검증 기준:

```text
OrderAdapter mode=disabled
submitted=0
buy_order_request 없음
sell_order_request 없음
```

최근 headless 검증에서 확인된 안전 상태:

```text
OrderAdapterResult(mode=disabled, submitted=0, blocked=0, failed=0, skipped=1)
```

## 10. 현재 작업트리 참고

이 문서는 구조 분석용 신규 문서이다.

문서 작성 시점에 이미 존재하던 변경 범위:

- `app/ui/app_gui.py`
- `app/utils/settings_schema.py`
- `app/services/ai_engine_provider.py`
- `app/services/aits_orchestrator.py`
- `data/logs/aits.log`
- `__pycache__` 산출물

따라서 `git status`에서 신규 문서만 보이지 않을 수 있다. 커밋 전에는 코드 변경과 검증 산출물을 분리해야 한다.

## END
