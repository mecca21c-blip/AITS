# AITS Local Data Lifecycle & Storage Policy v1

## 1. Purpose

This document defines the lifecycle, retention, summary, archive, and optimization policy for LOCAL engine data.

LOCAL must not become a system that accumulates unlimited raw data and reads it directly forever. Long-running AITS installations must keep recent raw data useful, convert older data into summaries and learning candidates, and prevent database or log growth from degrading startup, UI rendering, and Preview decision performance.

This policy is the reference for future LOCAL settings UI and storage implementation work. It does not authorize live trading, order execution, Router bypass, RiskGuard bypass, or automatic active model changes.

## 2. Core Principle

The LOCAL data lifecycle follows this path:

`Raw Data -> Feature Summary -> Reflection Label -> Local Learning Memory -> Current Decision Preview`

Core rules:

- Recent raw data may be used in detail.
- Older raw data is summarized or aggregated before use.
- Older raw data is not used directly in normal LOCAL decision paths.
- LOCAL must not load the full raw history on every decision.
- Unverified learning candidates must not be automatically promoted to an active model.
- Trading actions must still pass through Router, RiskGuard, and Execution safety layers.

## 3. Data Categories

### A. Raw Market Data

- Price and candle history.
- Volume history.
- Per-symbol scan results.
- Orderbook or tick-level execution snapshots, if introduced, are high-volume storage and must be treated as a separate high-risk retention class.

### B. Decision / Preview Data

- LOCAL scores.
- AI Preview decisions.
- Watch, entry, exit, and rotation candidates.
- Confidence, score, and condition snapshots.

### C. Reflection Data

- Stop-loss and take-profit review candidates.
- Missed exit timing candidates.
- Missed rotation opportunity candidates.
- Good wait decisions.
- Risk-avoidance decisions.

### D. Trading / Execution Records

- Order records.
- Fill records.
- Position changes.
- Return and performance records.
- In current Shadow/Preview operation, the `submitted=0` principle remains in force unless a separate live-execution Goal explicitly changes it.

### E. Summary / Feature Data

- Daily performance summaries.
- Per-symbol win-rate and PnL summaries.
- Strategy-condition performance summaries.
- Reflection label summaries.
- Recent and cumulative pattern features.

### F. Runtime Logs

- Application logs.
- ProviderConnectionProof logs.
- LocalEngineProof logs.
- Debug and trace logs.
- Long-term audit records and short-term rotating logs must be separated.

## 4. Default Retention Policy

Recommended defaults:

- 상세 데이터 30일: detailed price, scan, and decision logs are retained in raw form for 30 days.
- AI Preview and Decision detailed logs: 30 days.
- 복기 1년: Reflection events are retained for 1 year by default.
- Order and fill records: retained indefinitely by default.
- Daily and per-symbol summaries: retained indefinitely by default.
- Orderbook or sub-second snapshots: not stored by default, or retained only for a very short period when explicitly enabled.
- Raw detail data: summarized after 30 days.
- Raw compressed archive candidates: after 90 days.
- User delete-or-keep review: after 1 year for old raw data.
- Database optimization: weekly by default.
- Data size warning: 1GB and above.
- Full raw direct query: forbidden in normal LOCAL decision paths.

These defaults are intended to keep AITS usable after more than one year of operation without requiring the LOCAL engine to repeatedly scan large raw tables.

## 5. LOCAL Runtime Read Policy

LOCAL decision and Preview paths may read:

- Recent 7 to 30 days of detailed data.
- Recent 30 days of condition-performance data.
- Recent 90 days of Reflection summaries.
- One year of cumulative summary and feature data.
- Verified Local Learning Memory.

LOCAL decision and UI rendering paths must not read:

- One year of raw price, scan, and decision logs directly.
- Full raw scan history for all symbols.
- Unverified Reflection candidates as automatic learning input.
- Large raw datasets just to render normal UI screens.

The runtime read path should prefer small current-state snapshots, feature tables, summary tables, and verified memory over direct raw-history scans.

## 6. Summary / Compression Policy

Older raw data must be converted into summary records before it leaves the direct decision path.

Recommended summary groups:

- `daily_symbol_summary`
- `strategy_condition_summary`
- `reflection_event_summary`
- `missed_exit_summary`
- `rotation_opportunity_summary`
- `wait_success_summary`
- `risk_avoided_summary`

Policy:

- Raw data is excluded from normal direct decision paths after summary.
- Summary data becomes the LOCAL feature source for long-term patterns.
- Raw deletion requires successful summary generation first.
- Summary failure blocks raw deletion.
- Compression or archive should preserve enough audit context to explain later LOCAL Preview behavior.

## 7. Archive / Cleanup Policy

Cleanup stages:

- After 30 days, detailed data becomes a summary candidate.
- After 90 days, raw data becomes an archive candidate.
- After 1 year, raw data should require a user delete-or-keep policy.
- Order and fill records are not deleted by default.
- Log files are rotation and compression candidates.
- Database optimization runs only at safe times.

Cleanup must be conservative. AITS should prefer dry-run previews, clear user-facing counts, and recoverable archives before destructive cleanup.

## 8. LOCAL Settings UI Contract

LOCAL settings are about data lifecycle and learning policy, not qwen, mistral, Ollama, or model selection.

General mode should expose:

- Recommended automatic management.
- Detailed data retention period.
- Reflection data retention period.
- Automatic summary for old data.
- Automatic optimization schedule.
- Data size warning threshold.

Advanced mode may expose:

- Recent data weight.
- Reflection event scope.
- Learning candidate application policy.
- Block unverified learning.
- Raw archive threshold.
- Manual database optimization.
- Cleanup dry-run preview.

Default settings:

- Recommended automatic management: ON.
- Detailed data retention: 30 days.
- Reflection data retention: 1 year.
- Automatic summary: ON.
- Automatic optimization: weekly.
- Data size warning: 1GB.
- Block unverified learning: ON.

## 9. Safety Rules

- LOCAL cleanup must not arbitrarily delete order or fill records.
- Bulk cleanup, archive, compression, and database optimization must not run during active trading.
- Raw data must not be deleted when summary generation fails.
- Cleanup results must be logged without exposing secrets.
- Learning candidates must not be automatically promoted to an active model before verification.
- LOCAL must not bypass Router, Execution, or RiskGuard.
- The `submitted=0` principle remains in force unless a separate live-execution Goal explicitly authorizes otherwise.

## 10. Future Implementation Goals

- `AITS-LOCAL-DATA-02 Storage Map Audit`: audit current database, log, and file storage locations and identify actual growth risks.
- `AITS-LOCAL-DATA-03 Summary Schema Design`: define summary table or file schemas for LOCAL features.
- `AITS-LOCAL-DATA-04 Local Data Settings UI`: add data lifecycle controls to the LOCAL settings UI.
- `AITS-LOCAL-DATA-05 Cleanup/Archive Dry-Run`: calculate cleanup targets without deleting data.
- `AITS-LOCAL-DATA-06 Safe Compaction`: safely execute database optimization and log rotation.

## 11. ChatGPT Verification Summary

LOCAL is not an engine that reads unlimited raw data forever. It should use recent raw data, cumulative summaries, verified Reflection labels, and checked learning candidates.

The long-term path is `Raw Data -> Feature Summary -> Reflection Label -> Local Learning Memory -> Current Decision Preview`.

To remain fast after more than one year, AITS needs retention, summary, archive, and optimization policies. The default policy is detailed data for 30 days, Reflection for 1 year, summaries retained indefinitely, a 1GB warning threshold, and weekly optimization.

The LOCAL settings UI should manage data lifecycle and learning application policy. It must not become a qwen, mistral, Ollama, or model picker UI.
