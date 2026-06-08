# AITS Packaged Toggle Asset / Style Resource Fix v1

## 1. Goal

AI-ARCH-19-H-FIX1 fixes the packaged AITS top ON/OFF toggle visual asset issue.

Scope:

- trace the top ON/OFF toggle widget and asset path
- include the required toggle PNG assets in the main app PyInstaller bundle
- rebuild the packaged app
- run packaged smoke verification
- keep all runtime/trading behavior unchanged

This Goal does not redesign the UI, change ON/OFF behavior, modify Router/Execution/Order/RiskGuard, or change requirements.

## 2. Existing Problem

AI-ARCH-19-H visual verification found that the top ON/OFF toggle looked broken in packaged `AITSMain.exe`.

Relevant implementation:

- `app/ui/app_gui.py` creates the top header power control.
- `_refresh_header_png_slots()` attempts to load:
  - `header_toggle_on.png`
  - `header_toggle_off.png`
- `_aits_ui_asset_path()` resolves those files under:
  - `assets/ui`

Existing source assets:

| Asset | Source path | Size |
| --- | --- | ---: |
| `header_toggle_on.png` | `C:\AITS\assets\ui\header_toggle_on.png` | `48,017` bytes |
| `header_toggle_off.png` | `C:\AITS\assets\ui\header_toggle_off.png` | `48,017` bytes |

Packaged dist before this fix contained many dependency assets, but did not contain these AITS-specific toggle PNG files.

## 3. Cause Analysis

The toggle code already had a fallback style-only switch, but the intended polished header toggle uses PNG assets when available.

Packaged path behavior:

- In PyInstaller onedir mode, `app/ui/app_gui.py` resolves under `_internal`.
- Therefore the packaged runtime expects AITS assets at:

```text
dist/AITSMain/_internal/assets/ui/header_toggle_on.png
dist/AITSMain/_internal/assets/ui/header_toggle_off.png
```

The main app spec did not include these source files in `datas`, so packaged runtime could not load them with `QPixmap`.

Root cause:

- asset packaging omission in `aits_app.spec`

Not root cause:

- ON/OFF behavior logic
- trading toggle handler
- Router/Execution/Order integration
- PySide6 platform plugin
- runtime data path

## 4. Modified Files

Modified:

- `aits_app.spec`

Added:

- `app/docs/aits_packaged_toggle_asset_style_fix_v1.md`

Not modified:

- `run.py`
- `app/ui/app_gui.py`
- `app/utils/prefs.py`
- `app/utils/keys.py`
- `app/storage/journal_store.py`
- `requirements.txt`
- Router/Execution/Order/RiskGuard files

## 5. Asset / Resource / Spec Change

Added only the two required toggle PNG files to the main app PyInstaller `datas` list:

```python
datas += [
    (str(project_root / "assets" / "ui" / "header_toggle_on.png"), "assets/ui"),
    (str(project_root / "assets" / "ui" / "header_toggle_off.png"), "assets/ui"),
]
```

No broad asset directory collection was added.
No runtime code path helper was changed.
No UI logic was changed.

Packaged dist confirmation after rebuild:

| Packaged file | Size |
| --- | ---: |
| `C:\AITS\dist\AITSMain\_internal\assets\ui\header_toggle_on.png` | `48,017` bytes |
| `C:\AITS\dist\AITSMain\_internal\assets\ui\header_toggle_off.png` | `48,017` bytes |

## 6. Rebuild Result

py_compile:

```powershell
.\.venv\Scripts\python.exe -m py_compile run.py app\ui\app_gui.py
```

Result:

- passed

PyInstaller rebuild:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm aits_app.spec
```

Result:

- build succeeded
- elapsed wall time: about 5 minutes 44 seconds
- executable regenerated under `C:\AITS\dist\AITSMain`

Build warnings observed:

- `collect_dynamic_libs - skipping library collection for module 'sklearn' as it is not a package`
- hidden import `pycparser.lextab` not found
- hidden import `pycparser.yacctab` not found
- hidden import `scipy.special._cdflib` not found
- `google.generativeai` package deprecation warning

These warnings did not block build or packaged smoke.

## 7. Packaged Execution Result

Packaged smoke command:

```powershell
.\dist\AITSMain\AITSMain.exe
```

Observation:

- observed for 60 seconds
- process stayed alive
- process was stopped after observation
- no fatal traceback observed
- no missing asset exception observed
- `app_gui.window_show` logs observed
- `mplfinance` chart render logs observed

Runtime log signals:

```text
root_dir=C:\AITS\dist\AITSMain
data_dir=C:\Users\mecca\AppData\Local\AITS\data
UI launched via legacy-compatible entry
[AITS][StartupPerf] app_gui.window_show.end
[AITS][Chart] render_mode | used=mplfinance | reason=ok
```

Non-fatal stderr warnings still observed:

- matplotlib font cache initialization
- Qt signal disconnect `RuntimeWarning` messages
- `[SSOT] illegal settings access path`
- stylesheet parse warnings on unrelated settings/status frames
- account permission/zero balance warnings

These are pre-existing packaged smoke warnings and are not caused by the toggle asset inclusion.

## 8. Runtime Path Result

Dist runtime data scan after rebuild and smoke:

- no `secret.bin`
- no `secrets.json`
- no `prefs.json`
- no `aits_journal.sqlite3`
- no `local_ai_registry`
- no `.log` file

LocalAppData runtime files after smoke:

| Runtime item | Location |
| --- | --- |
| `prefs.json` | `C:\Users\mecca\AppData\Local\AITS\data\prefs.json` |
| `secret.bin` | `C:\Users\mecca\AppData\Local\AITS\data\secret.bin` |
| `secrets.json` | `C:\Users\mecca\AppData\Local\AITS\data\secrets.json` |
| `aits.log` | `C:\Users\mecca\AppData\Local\AITS\data\logs\aits.log` |

The AI-ARCH-19-G-FIX1 runtime path policy remains intact.

## 9. Safety Result

Safety scan found no critical live/order/training signals in the LocalAppData log for this smoke:

- submitted order: not observed
- live order: not observed
- buy/sell execution: not observed
- OrderAdapter execution: not observed
- ExecutionBridge execution: not observed
- Local AI trainer auto-run: not observed
- model auto-approval: not observed
- active_model auto-setting: not observed
- API key input/save/test: not performed

Console output did include normal startup refresh messages such as account fetch and ticker refresh, with `live_trade=False` in earlier packaged verification context. No trade action was performed.

## 10. Decision

Decision: `GO_FOR_USER_VISUAL_CONFIRMATION`

Why:

- root cause was identified as missing packaged AITS toggle PNG assets
- required PNG files are now included in `dist/AITSMain/_internal/assets/ui`
- packaged app rebuild succeeded
- packaged smoke stayed alive
- no fatal traceback or missing asset error observed
- dist runtime data remains clean
- safety posture remains unchanged

Remaining limitation:

- Codex did not perform visual screenshot judgment.
- Final visual confirmation of the ON/OFF toggle appearance remains a user/ChatGPT screenshot review step.

## 11. Remaining Issues

Non-blocking packaged UI warnings remain from earlier smoke runs:

- Qt signal disconnect warnings
- stylesheet parse warnings in unrelated settings/status frames
- `[SSOT] illegal settings access path`
- account permission/zero-balance warnings

Possible future Goals:

- packaged stylesheet warning cleanup
- SSOT illegal settings access path diagnosis
- packaged UI visual confirmation record after screenshot review

## 12. Safety / Non-Goals

This Goal did not:

- change ON/OFF behavior
- change real trading enable/disable logic
- modify Router/Execution/Order/RiskGuard
- modify app UI layout beyond packaged asset inclusion
- modify `app/ui/app_gui.py`
- modify `run.py`
- modify requirements
- install or uninstall dependencies
- enter or save API keys
- run API connection tests
- start Local AI training
- auto-approve a model
- commit dist/build/runtime data

This fix is an asset packaging fix, not a live trading or deployment approval.
