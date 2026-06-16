# AITS Remaining Tabs UI-First Roadmap v1

## 1. Purpose

This document defines the UI-first roadmap for the remaining major AITS tabs after the AI Policy Center was separated into its own dedicated tab.

The goal is to avoid repeating the previous pattern where runtime behavior, legacy widgets, duplicate owners, and UI copy were mixed together. Each tab should first have a clear active UI owner, visible structure, empty/error states, and light read-only connections. Deep runtime integration must be handled later in separate Goals.

This roadmap is documentation-only. It does not authorize Router, Execution, Order, RiskGuard, provider, API key, database cleanup, or packaging work.

## 2. Active Tab Map

| User tab | Active widget / class | Creation owner | File location | Bottom nav | Legacy status | Dedicated tab | Save relevance |
|---|---|---|---|---|---|---|---|
| AITS 종목관리 | `WatchlistTab` plus app_gui managed-pool insertions | `MainWindow` tab setup, then `WatchlistTab` | `app/ui/app_gui.py`, `app/ui/tabs/watchlist_tab.py` | index 0, `_on_bottom_nav_clicked(0)` | Mixed. `WatchlistTab` owns legacy table/refresh paths while `app_gui.py` hides some old controls and inserts managed pool UI. | Partial | Not a footer-save owner yet. Watchlist/session persistence should remain scoped until a later Goal. |
| 매매기록 | `TradesTab` | `MainWindow` tab setup | `app/ui/tabs/trades_tab.py` | index 1, `_on_bottom_nav_clicked(1)` | Mostly simple table UI. Export exists but should not drive the next UI-first pass. | Yes | No primary footer-save role. |
| 투자현황 | `PortfolioTab` | `MainWindow` tab setup | `app/ui/tabs/portfolio_tab.py` | index 2, `_on_bottom_nav_clicked(2)` | Dedicated tab with holdings and AI decision display copy that needs safety/UI separation. | Yes | No primary footer-save role. |
| AI 정책 센터 | `AIPolicyCenterTab` | `MainWindow` tab setup | `app/ui/tabs/ai_policy_center_tab.py` | index 3, `_on_bottom_nav_clicked(3)` | Completed reference path. `StrategyTab` remains compatibility-only and is not the default visible policy surface. | Yes | Footer save dispatcher stores `ui_state.ai_policy_snapshot`. |
| 공통설정 | `QWidget` built by `_init_settings` | `MainWindow._init_settings` | `app/ui/app_gui.py` | index 4, `_on_bottom_nav_clicked(4)` | Large app_gui-owned mixed surface. Provider/API/LOCAL recovery is complete, but polish remains. | No | Footer save falls back to existing `_on_save_settings`. |
| 메인 대시보드 | App shell / dashboard-like surfaces, not a bottom-nav tab | `MainWindow` shell/status/detail areas | `app/ui/app_gui.py` | No confirmed bottom-nav index | Active path is app_gui-internal and should be audited before redesign. | No | No tab-specific save owner. |

## 3. Current Readiness By Tab

### AITS 종목관리

Current readiness: partial / mixed.

The active tab is `WatchlistTab`, but `app_gui.py` also inserts managed-pool UI and hides several original `WatchlistTab` controls. This makes the visual owner less clear than the AI Policy Center path.

Current risks:

- Managed, candidate, watch, and block states are not yet presented as one clear user model.
- Some legacy watchlist controls still exist behind app_gui-managed UI decisions.
- Empty, loading, and error states need clearer user-facing copy.
- Add, exclude, refresh, and candidate actions need role clarity.
- This tab must not imply automatic buy behavior.

### 투자현황

Current readiness: partial.

`PortfolioTab` is a dedicated active tab with summary and holdings-related display, but the user-facing distinction between actual holdings, preview analysis, and AI condition text needs more visible separation.

Current risks:

- Actual holdings and preview/condition labels can read as one layer.
- API/load failure and no-holdings states should be clearer.
- Sell-like copy such as AI waiting/condition labels must stay display-only and not look like an action.
- No order action should be added in the UI-first pass.

### 매매기록

Current readiness: usable but basic.

`TradesTab` is a dedicated table tab. It currently fits actual trade-record review better than a broader history center.

Current risks:

- Actual fills, Preview decisions, and Reflection records are not visually separated.
- Empty states and filters are minimal.
- Export exists, but export polish should be handled after category/filter UI is clear.

### 공통설정

Current readiness: partial / recovered.

Provider/API/LOCAL ownership has been recovered and should not be disturbed without an explicit provider Goal.

Current risks:

- The tab remains a large app_gui-owned mixed settings surface.
- Future polish should preserve the Provider Engine Root-Cause contract.
- Provider selection, connection verification, and persistence roles must stay separated.

### 메인 대시보드

Current readiness: not yet defined as a dedicated tab.

The main dashboard appears to be app shell and app_gui-owned status/detail surfaces rather than a clean bottom-nav tab. It needs a separate active path audit before a dashboard redesign.

Current risks:

- Dashboard-like widgets may be spread across app shell, header, status rows, detail chart, and managed pool areas.
- Adding dashboard helpers before ownership is mapped would repeat the earlier legacy-overwrite problem.

### AI 정책 센터

Current readiness: reference complete.

The active path is a dedicated `AIPolicyCenterTab`, and footer save dispatch stores only the policy snapshot. This is the model for future tab cleanup: dedicated owner first, UI clarity second, runtime integration later.

## 4. UI-First Target By Tab

### AITS 종목관리

Target:

- Present one clear managed-list surface.
- Separate candidate, 관심/관리, and 제외 states.
- Add clear empty, loading, and refresh-failed states.
- Make button roles explicit: add, exclude, refresh, inspect.
- Keep all copy display/management focused.
- Do not add automatic buy, sell, Router, Execution, Order, or RiskGuard behavior.

Light connection:

- Read existing managed-pool rows and current watchlist/blocklist state.
- Use existing refresh paths only for display.
- Keep persistence scoped to existing list settings until a later Goal defines save ownership.

### 투자현황

Target:

- Show total assets, cash, holding valuation, and PnL as summary cards.
- Provide a clear no-holdings state.
- Provide API/load failure state.
- Label actual holdings separately from Preview/condition analysis.
- Keep any AI/LOCAL/GPT/GEMINI analysis copy as display-only.

Light connection:

- Reuse existing `PortfolioTab.refresh` and `get_summary_metrics` style data where available.
- No order, sell, rebalance, or RiskGuard action.

### 매매기록

Target:

- Split visible history into actual fills, Preview decision records, and Reflection records.
- Add empty state and simple filters.
- Keep export as a later polish step.
- Avoid presenting Preview or Reflection as submitted orders.

Light connection:

- Reuse existing trade table and event refresh.
- Read-only display only.

### 공통설정

Target:

- Preserve recovered Provider/API/LOCAL contract.
- Polish copy and density only when explicitly scoped.
- Do not reintroduce legacy provider writers or duplicate save/connection paths.

Light connection:

- Existing provider selection, connection proof, local self-check, and settings save paths only.

### 메인 대시보드

Target:

- Define a future dashboard with AI briefing, policy status, engine status, and symbol summary.
- Audit active ownership before implementation.
- Avoid attaching another dashboard surface over existing app_gui shell widgets.

Light connection:

- Read existing status snapshots and summaries only after active path is mapped.

## 5. Light Connection Scope

Allowed in the UI-first phase:

- Read existing UI state, cached prefs, and display snapshots.
- Use existing tab refresh methods for display.
- Show empty, loading, and error states.
- Update copy, labels, cards, filters, and summary panels.
- Store tab-specific UI snapshots only where a clear existing owner exists.

Not allowed in the UI-first phase:

- New trading runtime behavior.
- New provider/API connection behavior.
- New database cleanup, migration, archive, or export execution.
- New RiskGuard, Execution, Order, or Router side effects.

## 6. Forbidden Runtime/Trading Scope

The following are forbidden for this phase:

- Router connection.
- Execution connection.
- Order connection.
- RiskGuard live application.
- Real order submission.
- Buy/sell button activation.
- Automatic buy, automatic sell, forced sell, or rebalance execution.
- Live trading mode changes.
- DB bulk migration or cleanup.
- API key or secret modification.
- Provider connection logic changes.
- PyInstaller or packaged executable runs.

All UI-first tab work must keep submitted order behavior unchanged and preserve the `submitted=0` expectation unless a later live-execution Goal explicitly authorizes otherwise.

## 7. Recommended Implementation Order

1. `UI-MANAGED-01` - AITS 종목관리 active owner cleanup and UI-first managed list.
2. `UI-PORTFOLIO-01` - 투자현황 summary, empty, failure, and Preview/actual separation.
3. `UI-TRADES-01` - 매매기록 category and filter UI.
4. `UI-DASHBOARD-01` - 메인 대시보드 active path audit and dedicated dashboard plan.
5. `UI-SETTINGS-POLISH-01` - 공통설정 polish after provider ownership remains stable.

This order prioritizes tabs where the active owner is already a real tab and where UI clarity can improve without runtime integration.

## 8. Next Goal: UI-MANAGED-01

Recommended next Goal:

`UI-MANAGED-01 AITS Managed Symbols UI-First Cleanup`

Scope:

- Audit the active AITS 종목관리 owner.
- Confirm where `WatchlistTab` ends and app_gui managed-pool UI begins.
- Remove or hide duplicate visible ownership only if required.
- Present candidate / managed / excluded states clearly.
- Add empty, loading, and refresh-failed states.
- Clarify add, exclude, inspect, and refresh buttons.
- Keep all actions display/list-management only.
- Do not connect to Router, Execution, Order, RiskGuard, or real buy/sell behavior.

Acceptance criteria:

- The user can understand which symbols are managed, candidates, or excluded.
- Empty and failure states are visible and non-technical.
- No buy/sell or live trading action is introduced.
- No provider/API/LOCAL path is changed.

## 9. ChatGPT Verification Summary

AITS now has a clear UI-first roadmap for the remaining tabs. The active bottom-nav tab map is: AITS 종목관리 uses `WatchlistTab` with app_gui managed-pool additions; 매매기록 uses `TradesTab`; 투자현황 uses `PortfolioTab`; AI 정책 센터 uses the dedicated `AIPolicyCenterTab`; 공통설정 is app_gui-owned through `_init_settings`; 메인 대시보드 is not yet a clean bottom-nav tab and needs a separate active-path audit.

The recommended implementation order is AITS 종목관리, 투자현황, 매매기록, 메인 대시보드, then 공통설정 polish. This phase allows only light UI/display connections and forbids Router, Execution, Order, RiskGuard, real order submission, live trading behavior, provider connection changes, database cleanup, and packaging.
