# AITS AI Policy Center Readiness & Safety Audit v1

## 1. Purpose

This audit records the active UI ownership, visible controls, side effects, safety risks, and cleanup direction for the AITS AI Policy Center.

The goal is not to patch behavior in this document. The goal is to prevent another helper-on-top-of-helper regression by identifying the active path, duplicate or legacy surfaces, last writers, and high-risk copy before UI-POLICY-02 changes any code.

## 2. Active Tab Ownership

The visible tab is created in `app/ui/app_gui.py`.

Active creation path:

1. `MainWindow` creates `self.tab_strategy = StrategyTab(self, parent=self.tabs)`.
2. `MainWindow._install_ai_policy_center()` inserts the AI Policy Center at the top of that `StrategyTab`.
3. `MainWindow._wrap_legacy_strategy_policy_area()` moves the original `StrategyTab` widgets into a collapsed legacy container.
4. The tab is added as `AI 정책 센터`.

Active owner map:

| Area | Owner | File | Notes |
| --- | --- | --- | --- |
| Tab container | `self.tab_strategy` | `app/ui/app_gui.py` + `app/ui/tabs/config_tabs.py` | `StrategyTab` remains the tab widget. |
| AI Policy Center hero | `_build_ai_policy_center_widgets` | `app/ui/app_gui.py` | Active top surface. |
| Legacy strategy settings | `_wrap_legacy_strategy_policy_area` | `app/ui/app_gui.py` | Original `StrategyTab` UI is collapsed, not deleted. |
| Strategy controls | `StrategyTab` | `app/ui/tabs/config_tabs.py` | Still live when legacy container is opened. |
| Asset policy drawer | `_build_asset_policy_panel` | `app/ui/app_gui.py` | Separate detail-chart policy surface, not the active AI Policy Center tab. |

## 3. Section Map

Active AI Policy Center sections:

| Section | Visible text / role | Owner |
| --- | --- | --- |
| Header | `AI 운용 프로필 센터` | `_build_ai_policy_center_widgets` |
| Guidance | 운용 철학 and Runtime Preview explanation | `_build_ai_policy_center_widgets` |
| Flow label | `운용 프로필 -> 종목 Override -> AI Runtime Preview` | `_build_ai_policy_center_widgets` |
| Presets | 초보 안정형, 균형 운용형, 단기 공격형, 관망 스윙형, AI 자율 극대형 | `_apply_ai_policy_preset` |
| Style | 안정형, 균형형, 공격형, AI 자율형 | `_build_ai_policy_style_card` |
| Sliders | 리스크 수준, 관망 성향, AI 자율도 | `_build_ai_policy_slider_card` |
| Summary | 현재 AI 운용 프로필 | `_sync_ai_policy_summary` |
| Local runtime notice | LOCAL/GPT/GEMINI Preview engine notice | `_build_ai_policy_center_widgets` |
| Advanced policy toggle | Shows only a small explanatory advanced container | `_toggle_advanced_policy_container` |
| Legacy policy toggle | Shows collapsed original StrategyTab UI | `_toggle_legacy_policy_container` |

Legacy StrategyTab sections still present behind the collapsed area:

| Section | Owner | Risk note |
| --- | --- | --- |
| Strategy calculation tendency | `StrategyTab._build_aggressiveness_section` | Medium: AI/strategy sensitivity copy. |
| Rotation | `chk_rotation_enabled`, interval, count | High: rotation can imply sell/replacement behavior. |
| Order/risk amount | order amount, max cap, downscale | High: may influence future order sizing. |
| TP/SL | stop loss, take profit | High: exit policy surface. |
| Sell condition check | `btn_sell_test` | Medium: read-only/dry-run but sell-related copy. |
| Legacy AI recommendation | disabled recommendation/apply controls | High if re-enabled. |
| AI judge priority | disabled legacy advanced checkbox | High if re-enabled without Output Contract. |
| Save | `btn_save_apply` | Medium: persists strategy config and publishes refresh event. |

## 4. Control Inventory

| Display name | Variable / owner | Location | Signal | Handler | Persists? | Runtime/API/orders? | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI policy preset buttons | `btn_policy_preset_*` | `app_gui.py` | `clicked` | `_apply_ai_policy_preset` | Yes, via `_save_ai_policy_snapshot` | No orders/API; updates preview labels | Medium | Rename autonomous copy; emphasize profile only. |
| 운용 스타일 | `cmb_ai_policy_style` | `app_gui.py` | `currentTextChanged` | `_on_ai_policy_changed` | Yes, UI snapshot | No orders/API | Medium | Replace `AI 자율형` with safer profile wording. |
| 리스크 수준 | `slider_policy_risk` | `app_gui.py` | `valueChanged` | `_on_ai_policy_changed` | Yes, UI snapshot | No direct runtime/order | Medium | Keep as policy preview. |
| 관망 성향 | `slider_policy_wait` | `app_gui.py` | `valueChanged` | `_on_ai_policy_changed` | Yes, UI snapshot | No direct runtime/order | Low | Keep. |
| AI 자율도 | `slider_policy_autonomy` | `app_gui.py` | `valueChanged` | `_on_ai_policy_changed` | Yes, UI snapshot | No direct runtime/order | High copy risk | Rename to strategy discretion / review sensitivity. |
| 고급 정책 펼치기 | `btn_toggle_advanced_policy` | `app_gui.py` | `clicked` | `_toggle_advanced_policy_container` | No | No | Low | Keep, but ensure advanced copy stays preview-only. |
| 고급 정책 펼치기 legacy | `btn_toggle_legacy_policy` | `app_gui.py` | `clicked` | `_toggle_legacy_policy_container` | No | Reveals legacy StrategyTab | Medium | Make legacy status and risk clearer. |
| 설정 저장 | `btn_save_apply` | `config_tabs.py` | `clicked` | `_on_save_apply` | Yes, strategy commit | Publishes `ai.reco.refresh`; no direct order | Medium | Keep as persistence only; label should remain clear. |
| 매도 조건 점검 | `btn_sell_test` | `config_tabs.py` | `clicked` | `_on_sell_test_clicked` | No | Fetches holdings; no order | Medium | Keep order-none copy. |
| 로테이션 조건 계산 | `chk_rotation_enabled` | `config_tabs.py` | `toggled` | `_on_rotation_enabled_changed` | On save | Can affect future strategy evaluation | High | Keep Preview/Shadow and approval copy. |
| 주문금액 축소 계산 | `chk_allow_downscale` | `config_tabs.py` | `toggled` | `_mark_dirty` | On save | Future sizing impact | High | Keep Live validation warning. |
| 손절/익절 | `spn_stop_loss_pct`, `spn_take_profit_pct` | `config_tabs.py` | `valueChanged` | `_update_tp_sl_status` | On save | Future exit policy | High | Avoid AI-autonomous wording. |
| AI Output Contract 참고 우선 | `chk_ai_judge` | `config_tabs.py` | none active; disabled | none active | No | Disabled | High if enabled | Keep disabled until explicit contract. |
| 추천 미리보기 / 적용 비활성 | `btn_ai_refresh`, `btn_ai_apply` | `config_tabs.py` | disabled | none active | No | Disabled | High if enabled | Keep disabled or remove legacy UI. |

## 5. High-Risk Controls

High-risk surfaces:

- `AI 자율 극대형` preset and `AI 자율도` slider: can imply AI direct control.
- `AI 자율형` style value: can imply autonomous action.
- Rotation controls: can imply replacement or sell behavior.
- Order amount and downscale controls: can affect future sizing.
- TP/SL controls: exit policy surfaces.
- Sell condition check: safe today, but sell-related and holdings-reading.
- Legacy AI recommendation/apply controls: currently disabled but dangerous if reconnected.
- Legacy AI judge priority: currently disabled; must remain disabled without Output Contract and Router/RiskGuard policy.

## 6. Dangerous Copy / UX Risk

Current risky wording candidates:

| Copy | Risk | Recommendation |
| --- | --- | --- |
| `AI 자율 극대형` | Sounds like AI may act independently. | `전략 판단 민감도 높음` or `검토 민감도 높음`. |
| `AI 자율형` | Implies autonomous execution. | `전략 위임형 Preview` or safer non-execution wording. |
| `AI 판단 비중 확대` | Can sound like direct AI order authority. | `후보 평가에서 AI/전략 참고 비중 확대`. |
| `AI 중심` | Ambiguous authority. | `전략 계산 참고 비중 높음`. |
| `AI가 Runtime 판단을 준비합니다` | Could imply active runtime application. | Add `Preview only / 주문 없음`. |
| `AI Decision Gate` | English gate wording may imply execution gate. | Add human review / action blocked copy. |
| Legacy `AI 추천 적용하기` traces | Direct apply wording. | Keep disabled or remove; if visible, use `검토안 보기`. |

Safe copy direction:

- Use `Preview`, `Shadow`, `조건 계산`, `주문 없음`, `자동 적용 없음`.
- Mention `Router/RiskGuard 우회 없음`.
- Use `설정 저장` for persistence.
- Avoid `실행`, `자동매매`, `AI 직접 주문`, `전량매도 실행`, `적용하기` unless the control is disabled and clearly marked.

## 7. Signal & Side Effect Audit

AI Policy Center active signals:

- Preset buttons call `_apply_ai_policy_preset`.
  - Updates policy controls.
  - Saves `ui_state.ai_policy_snapshot`.
  - Calls `_sync_runtime_summary_labels`.
  - Does not call API providers, Router, Execution, Order, or RiskGuard.
- Policy style and sliders call `_on_ai_policy_changed`.
  - Updates summary.
  - Saves `ui_state.ai_policy_snapshot`.
  - Does not place orders or change provider runtime.
- Advanced and legacy toggles only change visibility.

Legacy StrategyTab signals:

- `btn_save_apply.clicked -> _on_save_apply`.
  - Commits strategy settings.
  - Publishes `ai.reco.refresh`.
  - Updates global status.
  - No direct order call found in this handler.
- `btn_sell_test.clicked -> _on_sell_test_clicked`.
  - Calls holdings and last sell-decision readers.
  - Displays a message with `실제 주문 없음`.
- Rotation, TP/SL, order amount, downscale controls mark dirty or update labels.
  - Persistence happens through save.

Side effect risks:

- Policy Center auto-saves UI snapshot on every change. It is UI-only, but the word `policy` can make it look stronger than it is.
- Strategy save publishes `ai.reco.refresh`; UI-POLICY-02 should verify consumer behavior before changing copy.
- Legacy hidden controls still exist. Disabled or collapsed does not equal removed.

## 8. Legacy / Duplicate Paths

Known duplicate or legacy surfaces:

- `StrategyTab` is still the tab widget and remains live inside the collapsed legacy policy container.
- `legacy_policy_content_container` hides, but does not remove, the old StrategyTab controls.
- `advanced_policy_container` and `legacy_policy_content_container` are separate toggles with similar labels.
- Common Settings still has legacy Basic/AI controls outside this tab; not active AI Policy Center ownership, but can confuse future audits.
- Asset policy drawer in `app_gui.py` is another policy surface outside the AI Policy Center tab.

UI-POLICY-02 should not assume that the top AI Policy Center is the only policy UI. It should explicitly decide whether legacy StrategyTab controls remain, move, or become read-only.

## 9. Safety Contract

The AI Policy Center must preserve:

- `submitted=0` for Preview/Shadow surfaces.
- No live order from policy controls.
- No direct buy/sell from AI policy controls.
- No Router/Execution/Order/RiskGuard bypass.
- No AI recommendation auto-apply.
- No high-risk control exposed as an enabled action without separate approval and confirmation.
- Save means persistence for next evaluation, not order execution.
- Preview/Shadow means review and calculation, not trading signal.

## 10. UI-POLICY-02 Cleanup Recommendation

Recommended patch scope:

1. Rename high-risk AI autonomy copy.
2. Make the top Policy Center summary explicitly `Preview only · 주문 없음`.
3. Split the two `고급 정책 펼치기` toggles into clear names:
   - `정책 설명 펼치기`
   - `레거시 전략 설정 열기`
4. Add a warning strip before opening the legacy StrategyTab area.
5. Keep legacy AI recommendation/apply disabled or remove from active layout.
6. Confirm `ai.reco.refresh` consumer behavior before changing save copy.
7. Keep Strategy Save as persistence-only and avoid `적용` wording.
8. Ensure asset policy drawer copy follows the same Preview/Shadow/no-order language.
9. Do not add new writers or duplicate state helpers; simplify ownership where possible.

UI-POLICY-02 acceptance criteria:

- All visible policy copy avoids direct order or AI-autonomy implication.
- Legacy high-risk controls are either hidden, disabled, or explicitly marked Preview/Shadow.
- Save/test/action roles are separated.
- No services, Router, Execution, Order, RiskGuard changes.
- No packaging run.

## 11. ChatGPT Verification Summary

- Active AI Policy Center is installed by `app_gui.py` into `StrategyTab`; the tab label is `AI 정책 센터`.
- The active top surface is `_build_ai_policy_center_widgets`.
- The original `StrategyTab` from `config_tabs.py` is still live, but moved into a collapsed legacy policy area.
- AI Policy Center controls save only a UI snapshot and do not directly call API providers, Router, Execution, Order, or RiskGuard.
- High-risk remaining copy is mostly autonomy/recommendation/apply wording and legacy strategy controls.
- UI-POLICY-02 should clean copy and legacy exposure, not add another helper path.
