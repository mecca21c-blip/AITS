# AITS Runtime Input System

## Purpose

The Runtime Input System keeps the UI and runtime snapshots aligned about which inputs the AI Runtime can currently observe.

It is display-only and read-only. It does not fetch data, run inference, calculate actions, or submit orders.

## Input Axes

- Market
- Portfolio
- Strategy
- Risk
- Command

## Safety Principles

- read-only
- no API call
- no inference
- no order/action
- no apply
- submitted=0
- real_order=False

## Data Sources

Runtime input attachments may only read already available local state:

- memory cache
- UI table `rowCount()`
- UI getter values
- ready flags
- source_hint/count only

The system must not copy large source data into the runtime snapshot. It records only compact indicators such as attached flags, counts, and source hints.

## Source Hints

The `source_hint` field explains why an input is considered attached:

- `ready_flag`: an existing boolean readiness flag was present
- `ui_cache`: an existing in-memory cache or UI table had rows/items
- `ui_control`: an existing UI control had a non-empty/enabled value
- empty string: no source detected

## Compact Runtime Status

The Compact Runtime Status summarizes attached inputs without expanding the panel height.

- 0 attached inputs: `입력상태: 데이터 대기 중`
- 1-3 attached inputs: show names, for example `입력상태: 시장/전략 연결`
- 4-5 attached inputs: show count, for example `입력상태: 4개 입력 연결`

The tooltip may show per-axis details:

- connected/waiting state
- source hint
- count summary

## Verification

Run the standard smoke verification after changes:

```powershell
cd C:\AITS
C:\AITS\.venv\Scripts\python.exe -m py_compile C:\AITS\run.py C:\AITS\app\ui\app_gui.py C:\AITS\app\services\decision_router.py
$env:QT_QPA_PLATFORM="offscreen"
C:\AITS\.venv\Scripts\python.exe C:\AITS\run.py --smoke-exit
```
