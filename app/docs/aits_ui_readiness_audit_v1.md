# AITS UI Readiness Audit v1

## 1. Goal

AI-ARCH-19 packaged/build 흐름을 일시 HOLD하고, 개발 모드 기준으로 AITS 메인 화면과 전체 탭의 구현 상태, 위험도, 다음 개발 우선순위를 감사한다.

이번 Audit은 코드 수정 없는 구조/상태 분석이다. PyInstaller build, packaged exe 실행, run.py/app_gui.py 수정, Router/Execution/Order/RiskGuard 수정은 수행하지 않는다.

## 2. Packaging HOLD 판단

AI-ARCH-19 계열에서 packaged build 가능성, AITSMain.exe 실행, runtime data path 분리, LightGBM/scipy packaged probe는 상당 부분 확인되었다.

그러나 현재 제품 상태는 packaging 완료보다 UI/기능 완성도가 더 큰 병목이다. 메인탭 외 주요 탭은 일부 동작 가능한 구현을 갖고 있지만, 표현 품질, AI 출력 계약, 설정/전략 안전 표면, 탭별 empty/error 상태 검증이 아직 부족하다.

판단:

- Packaging 작업은 HOLD.
- 개발 모드 기능 완성과 UI 신뢰도 정리를 우선한다.
- 실거래/주문 계층은 계속 미변경 상태를 유지한다.

## 3. 전체 UI 탭 목록

코드 기준 top-level 탭은 `app/ui/app_gui.py`에서 `QTabWidget`으로 구성된다. 탭 바는 현재 숨겨져 있으며, 실제 화면에서는 상단/사이드/버튼형 네비게이션과 결합되어 보일 수 있다.

| 탭/화면 | 생성 위치 | 주요 소유 파일 | 상태 분류 |
|---|---|---|---|
| 메인 화면 / 대시보드 | `app/ui/app_gui.py` | `app/ui/app_gui.py` | 표시 가능, 보강 필요 |
| AITS 종목관리 | `WatchlistTab` addTab | `app/ui/tabs/watchlist_tab.py` | 부분 사용 가능 |
| 매매기록 | `TradesTab` addTab | `app/ui/tabs/trades_tab.py` | 부분 사용 가능 |
| 투자현황 | `PortfolioTab` addTab | `app/ui/tabs/portfolio_tab.py` | 부분 사용 가능 |
| AI 정책 센터 | `StrategyTab` addTab | `app/ui/tabs/config_tabs.py` | 표시 가능, 고위험 보강 필요 |
| 공통설정 | `_init_settings()` | `app/ui/app_gui.py` | 부분 사용 가능, 정리 필요 |
| 로그인/계정 다이얼로그 | dialog | `app/ui/auth_dialogs.py` | 보조 기능, 문구 점검 필요 |
| AI 운영센터/브리핑 팝업 | popup/card | `app/ui/app_gui.py` | 표시 가능, AI 문구 보정 필요 |

## 4. 탭별 구현 상태

### 메인 화면 / 대시보드

상태: 표시 가능, 보강 필요.

메인 화면은 AI 브리핑, AI Intent, 엔진 상태, 실행 토글, 새로고침, 로그, 전량매도 버튼, 시장/종목 요약 영역을 포함한다. 화면 시작과 주요 패널 렌더링은 가능한 상태로 보인다.

문제는 AI 출력 표면이 아직 완성된 AI Output Contract와 fallback/Basic Preview/placeholder를 명확히 분리하지 못한다는 점이다. `AI Intent`, `AI 브리핑`, `판단 근거`, `다음 행동`, `AI 시나리오` 같은 표현이 실제 GPT/Gemini/Local AI 응답, Basic 계산, 대기 상태, 샘플 문구를 섞어 보여줄 수 있다.

### AITS 종목관리

상태: 부분 사용 가능.

`WatchlistTab`은 whitelist/blacklist, Top 거래대금 자동 로드, 가격/보유 표시, AI recommendation 이벤트 수신, worker 기반 refresh를 갖춘 실질 구현 탭이다.

다만 비동기 worker, top20 cache, watchlist SSOT, AI recommendation 이벤트, holdings/ticker fetch가 한 탭에 밀집되어 있다. 조용히 예외를 무시하는 구간도 많아, 실제 안정성은 별도 탭 smoke와 로그 기반 검증이 필요하다.

### 매매기록

상태: 부분 사용 가능.

`TradesTab`은 `app.db.trades_db.recent_trades()`를 통해 최근 거래를 표시하고 CSV export를 제공한다. `trades.recorded` 이벤트를 구독하여 refresh하는 구조도 있다.

현재는 표시/내보내기 중심 탭으로 상대적으로 위험도가 낮다. 다만 실제 journal/trade DB와 UI 컬럼 의미가 사용자가 이해하기 쉬운지, 빈 데이터/DB 오류/CSV export 실패 상태가 충분히 안내되는지 확인이 필요하다.

### 투자현황

상태: 부분 사용 가능.

`PortfolioTab`은 live holdings fetch, 보유종목 테이블, 최근 AI 판단 로그, TP/SL 및 AI 매도대기 컬럼을 포함한다.

계좌/API 상태에 의존하므로 위험도는 중간이다. API key 미설정, holdings fetch 실패, empty account, network error 상태에서 사용자가 "정상 보유 없음"과 "불러오기 실패"를 구분할 수 있어야 한다.

### AI 정책 센터

상태: 표시 가능, 고위험 보강 필요.

`StrategyTab`은 실행 상태, AI 매매 성향, 주문 설정, 심볼 제어, 사전 평가, watchlist 반영, AI 추천 생성/적용, 저장/적용 버튼을 포함한다.

이 탭은 기능 표면이 가장 넓고 실거래 안전과 가까운 설정을 다룬다. 코드상 "임시 반영", "저장/적용", "매도 테스트", rotation, order amount, TP/SL 등 사용자가 오해하면 위험한 조작 표면이 많다. 일반 노출 전 안전 문구, disabled state, preview/draft/live 구분, 저장 후 반영 범위 안내가 필요하다.

### 공통설정

상태: 부분 사용 가능, 정리 필요.

OpenAI/Gemini/Basic(Local) provider 선택, API key 저장/테스트, Upbit 연결 테스트, settings 저장 로직이 포함된다.

실제 API 호출 버튼이 존재하므로 테스트 버튼의 비용/네트워크/저장 범위 안내가 명확해야 한다. "Basic AI", "Local AI", "BASIC(Local)", "Basic Preview" 표현이 혼재되어 있어 AITS 규칙상 Basic Engine과 AI Engine Slot 구분을 더 분명히 해야 한다.

### 로그인/계정 다이얼로그

상태: 보조 기능, 문구 점검 필요.

계정 생성/로그인/아이디 저장 기능이 존재한다. 핵심 trading UI보다 위험도는 낮지만, 화면 문자열 인코딩/표현이 깨진 흔적이 있어 사용자 신뢰도 측면에서 점검 필요하다.

### AI 운영센터/브리핑 팝업

상태: 표시 가능, AI 문구 보정 필요.

상세 팝업은 AI 판단, 판단 근거, 다음 계획, 득점 수치, AI 시나리오, ETA를 보여준다. 다만 default/fallback 값이 "AI 기본값", "횡보 관찰형", confidence, ETA 같은 강한 의미를 가진 문구로 표시될 수 있다.

실제 AI Output Contract가 없을 때는 "AI 판단 없음", "Basic Preview 계산 기반 참고", "연결 대기"처럼 명확한 비-판단 표현으로 낮춰야 한다.

## 5. 탭별 위험도

| 탭/화면 | 위험도 | 이유 |
|---|---:|---|
| 메인 화면 / 대시보드 | 높음 | 사용자가 가장 먼저 보는 화면이며 AI 판단/실행 상태를 오해할 수 있음 |
| AITS 종목관리 | 중간~높음 | worker/API/cache/eventbus가 복잡하고 watchlist/blacklist 상태가 전략에 영향을 줄 수 있음 |
| 매매기록 | 낮음~중간 | 읽기/내보내기 중심이나 실제 주문 기록처럼 보이는 정보라 정확성이 중요 |
| 투자현황 | 중간 | 계좌/API 상태와 보유/AI Exit 표시가 사용자 행동에 영향을 줄 수 있음 |
| AI 정책 센터 | 높음 | 주문/전략/AI 추천/저장 적용 표면이 넓고 실거래 안전과 가까움 |
| 공통설정 | 중간~높음 | API key, provider, Upbit 연결 테스트, 실제 API 호출 버튼 존재 |
| 로그인/계정 다이얼로그 | 낮음 | 보조 기능이지만 문자열/저장 경로 신뢰도 점검 필요 |
| AI 운영센터/브리핑 팝업 | 높음 | AI narrative처럼 보일 수 있는 fallback/placeholder가 많음 |

## 6. 탭별 다음 조치

| 탭/화면 | 다음 조치 |
|---|---|
| 메인 화면 | AI Output Contract 기반 표시 규칙 정리, Basic Preview와 AI 판단 분리, fallback 문구 보정 |
| AITS 종목관리 | dev smoke, top20/worker 실패 상태 UI, WL/BL draft/apply 상태 문구 정리 |
| 매매기록 | empty/error/export smoke, DB source와 표시 컬럼 설명 정리 |
| 투자현황 | API 미설정/실패/빈 계좌 상태 분리, AI Exit 문구를 주문 신호가 아닌 참고 정보로 조정 |
| AI 정책 센터 | 위험 조작 숨김/비활성 후보 선정, preview/draft/live 상태 라벨, 저장/적용 범위 명시 |
| 공통설정 | provider terminology 통일, API 테스트 버튼 안내, key 저장/표시 상태 문구 정리 |
| 로그인/계정 | 인코딩/문구 점검, saved_id 저장 위치와 보안 안내 확인 |
| AI 운영센터/브리핑 | fallback narrative 제거 또는 낮춤, 실제 AI 응답 출처/시간/provider 표시 |

## 7. 메인탭 AI 출력 영역 상태

메인탭의 AI 출력 영역은 구조적으로는 충분히 많은 표면을 갖고 있다.

- `AI Intent`
- AI 브리핑 한 줄/팝업
- AI 판단/판단 근거/다음 행동
- AI 시나리오/ETA
- Active Engine / selected engine / actual engine
- Basic Preview와 provider별 상태 표시

하지만 현재 완성도는 "표시 기능은 있음, 의미 계약은 부족"이다.

특히 사용자는 문구만 보고 다음을 구분해야 한다.

- 실제 OpenAI/Gemini/Local AI 응답인지
- Basic 계산 기반 Preview인지
- Router preview/shadow 결과인지
- 아직 연결 대기/데이터 부족/fallback인지
- 주문 신호가 아닌 설명용 정보인지

현재 코드는 이 구분을 일부 시도하지만, 화면 전체에서 용어와 fallback 톤이 일관되지 않다.

## 8. AI 연결 후 문구 보정 필요 영역

우선 보정 대상:

1. "AI Intent", "AI 판단", "AI 시나리오"는 실제 AI Output Contract가 있을 때만 강하게 표시한다.
2. Basic 계산 결과는 "Basic Preview" 또는 "계산 기반 참고"로만 표시한다.
3. "다음 행동"은 주문/실행 지시처럼 읽히지 않게 "다음 확인 조건" 또는 "관찰 포인트"로 낮춘다.
4. "AI 점수", confidence, ETA는 산출 근거와 source가 없으면 숨기거나 "미산출"로 표시한다.
5. GPT/Gemini/Local AI/Basic 용어를 AITS 규칙에 맞게 통일한다.
6. API test 버튼은 실제 외부 API 호출임을 버튼 옆에 명확히 표시한다.
7. AI 연결 실패 시 "Basic 대기"가 실제 AI fallback처럼 보이지 않게 한다.

## 9. 숨김/보류 후보 UI

완성 전 숨김 또는 보류 후보:

- AI 정책 센터의 고위험 주문/전략 조작 일부: rotation, 매도 테스트, order amount, TP/SL 적용성 높은 컨트롤.
- AI 추천 적용 버튼: 추천 payload의 출처/검증/저장 범위가 UI에서 명확해질 때까지 보류.
- AI 시나리오/ETA/confidence 카드: 실제 AI Output Contract와 evaluation source가 없으면 약화 또는 접기.
- 공통설정의 실제 API 연결 테스트 버튼: warning copy와 비용/외부 호출 안내 전까지 보류 또는 확인 dialog 필요.
- 전량매도/실거래성 버튼: 현재 안전 원칙상 별도 승인 Goal 전까지 더 강한 guard/disabled/confirm 필요.

## 10. 즉시 수정 필요 UI

1. 메인 AI 브리핑/Intent 문구의 placeholder/fallback 정리.
2. "Basic AI" 표현을 AITS 규칙에 맞게 "Basic Preview" 또는 "Local AI"와 분리.
3. AI 판단/근거/다음행동이 실제 AI 응답인지 출처 표시.
4. AI 정책 센터의 저장/적용/임시 반영 상태를 사용자가 오해하지 않도록 라벨 정리.
5. API key/연결 테스트 버튼 주변의 실제 외부 호출 안내.
6. 탭 전반의 깨진 문자열/인코딩 흔적 점검.
7. 빈 데이터와 오류 상태를 구분하는 empty/error state 정리.

## 11. 다음 추천 Sprint 3개

### Sprint 1. UI-MAIN-01 Main AI Output Contract & Copy Fix

목표:

- 메인 화면 AI 브리핑/Intent/판단 근거/다음 확인 조건 문구 정리.
- Basic Preview와 AI Engine Output을 명확히 분리.
- provider/source/timestamp/contract status 표시.
- Router/Execution/Order 변경 없음.

완료 기준:

- AI Output Contract가 없으면 "AI 판단 없음"으로 표시.
- Basic 계산은 주문 신호처럼 보이지 않음.
- 메인 화면에서 사용자가 현재 상태를 오해하지 않음.

### Sprint 2. UI-SAFETY-01 Strategy/Common Settings Safety Hardening

목표:

- AI 정책 센터와 공통설정의 위험 컨트롤 상태를 정리.
- preview/draft/live, 저장/적용, API test, order-adjacent controls 문구 보강.
- 필요한 항목은 숨김/disabled/confirm으로 격리.
- Router/Execution/Order 변경 없음.

완료 기준:

- 설정 변경이 즉시 실거래로 이어진다는 오해가 없음.
- API key/test 버튼의 외부 호출 여부가 명확함.
- 고위험 조작은 별도 승인 Goal 전까지 안전하게 제한됨.

### Sprint 3. UI-TABS-01 Tab Functional Smoke & Empty/Error States

목표:

- AITS 종목관리, 투자현황, 매매기록 탭별 개발 모드 smoke.
- empty/error/loading 상태 정리.
- Watchlist top20/worker failure, holdings API failure, trades DB empty/export 상태 검증.
- 기능 코드는 필요한 범위에서만 보강하고 실거래 계층은 미변경.

완료 기준:

- 각 탭이 "사용 가능/표시만 있음/보류"로 다시 판정 가능.
- 탭별 오류가 사용자에게 조용히 묻히지 않음.
- 로그와 UI 상태가 맞아떨어짐.

## 12. 실거래 안전 영향 여부

이번 Audit은 코드 수정, packaging build, packaged exe 실행, API key 입력, 주문 버튼 조작, 자동 학습, Router/Execution/Order/RiskGuard 변경을 수행하지 않았다.

안전 판정:

- 실거래 연결 영향 없음.
- submitted/order/execution 발생 없음.
- active_model 자동 설정 없음.
- Local AI trainer 자동 실행 없음.
- requirements/dependency 변경 없음.
- packaging/build 실행 없음.

현재 권장 방향은 "기능 확장"보다 "사용자가 AI/Basic/Preview/Live 상태를 오해하지 않게 만드는 UI 신뢰도 정리"다.
