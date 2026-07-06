# AITS Live ON Preflight Provider Readiness Source v1

## Goal

`AITS-LIVE-ON-PREFLIGHT-PROVIDER-READINESS-SOURCE-FIX-01` separates the ON
preflight provider readiness gate from AI analysis freshness.

## Active Owner

- ON button owner: `MainWindow._on_run_toggled`
- Provider readiness owner: `MainWindow._build_on_preflight_provider_readiness_state`
- Existing engine readiness wrapper: `MainWindow._build_ai_engine_readiness_state`
- Final provider status renderer remains `MainWindow._render_ai_engine_state`

## Source Rule

ON preflight provider readiness uses the selected provider's connection snapshot:

- `strategy.ai_provider` / session selected provider normalized to `basic`, `gpt`, or `gemini`
- `_ai_connection_snapshots_by_provider`
- `_last_ai_connection_provider`
- `_last_ai_connection_status`
- `_resolve_ai_test_secret` for selected external provider key presence only

It does not use:

- latest AI opinion freshness
- response metadata presence
- tooltip text
- header label text
- trade log text

## Readiness Rule

- LOCAL/Basic: ready when the local connection status is ready, otherwise blocked.
- GPT/Gemini: ready only when key is present and the selected provider connection snapshot is `정상연결`.
- Latest connection failure blocks readiness.
- Missing key blocks readiness.
- `generation_not_fresh`, `generation_not_confirmed`, or missing response metadata do not lower provider readiness.

AI analysis freshness remains a separate AI opinion state. It can block a later
candidate or order-intent contract, but it must not make ON preflight say that a
connected provider is not connected.

## Diagnostics

Log prefixes:

- `[AITS][ProviderReadinessSource]`
- `[AITS][LiveOnProviderReadiness]`
- `[AITS][EngineStatusWriter]`

Harness modes:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-readiness-source-summary --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-readiness-regression-proof --provider gpt --observe-only
```

The regression proof verifies that a connected GPT/Gemini provider remains ON
preflight-ready even when AI analysis freshness is stale or missing. It does not
call external providers and does not submit orders.
