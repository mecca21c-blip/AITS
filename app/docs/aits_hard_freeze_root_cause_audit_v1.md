# AITS Hard Freeze Root Cause Audit v1

## Audit Scope

This audit uses Windows event records, the final persisted AITS log events, and source-path inspection. It does not restart ON or ask the user to reproduce a machine-level freeze.

## Observed Evidence

- Windows recorded Kernel-Power 41 and EventLog 6008 after the forced shutdown.
- No corresponding Python, Qt, Application Hang, Display 4101, or WHEA event was found in the inspected window.
- The AITS process reached live ON and continued writing runtime events until the log stopped abruptly.
- The live UI thread ran full curation, feature generation, model training, and calibration scans after outcome checkpoint evaluation.
- The same live session allowed a visible `mplfinance` background render in low-resource mode.
- Managed Pool candidate and evaluation events repeated at a short cadence and amplified concurrent load.

Kernel-Power confirms an unclean power loss but does not identify the initiating component. The strongest AITS-side contributors are therefore classified as synchronous live learning scans plus background native chart rendering, with loop cadence as a pressure multiplier. A GPU driver fault is not proven by the available event records.

## Live Learning Safety

Live runtime may append factual outcome checkpoints. It may not automatically run full dataset curation, feature regeneration, model training, or calibration. The settings below default to false:

- `learning_pipeline_auto_run_enabled`
- `local_model_training_auto_run_on_live`
- `calibration_auto_run_on_live`
- `curation_auto_run_on_live`
- `feature_pipeline_auto_run_on_live`

Heavy learning jobs require an explicit manual command or harness workflow. The guard records each blocked pipeline without inventing outcomes, model state, or metrics.

## Chart And Runtime Safety

Low-resource mode defaults to background chart rendering disabled and manual-only chart rendering. The startup chart gate is 60 seconds, displayed candles are capped at 80, and subplots remain disabled. Backing market and indicator data remains available to the decision payload.

Managed Pool status work uses a reduced cadence for the first 60 seconds and a bounded cadence afterward. Existing AI pending guards and indicator batches remain in force.

## Hard Freeze Marker

`data/runtime/aits_last_session_state.json` is runtime-only evidence and is never a commit target. ON_ACTIVE writes `clean_shutdown=false`, resource snapshots update its heartbeat, and normal OFF/application close writes `clean_shutdown=true`. A later start reports a previous unclean marker with the last successful stage, component, and resource snapshot.

## Ultra Safe Defaults

The stability-first profile enables low-resource and ultra-safe startup, delays AI and ETA scheduling, disables background chart rendering, lowers market/indicator batches, batches UI logs, and keeps table refresh throttled. It does not weaken holdings, valuation, decision state, outcome append, reconciliation, RiskGuard, LivePreflight, or execution safety.

## Observe-Only Validation

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode hard-freeze-root-cause-audit-v1-summary --observe-only
```

The summary reads existing evidence only. It does not start AITS, toggle ON, invoke providers, or place orders.
