# AITS Provider Key Resolution Bootstrap Trace v1

## Goal

`AITS-AI-PROVIDER-KEY-RESOLUTION-BOOTSTRAP-ACTUAL-TRACE-FIX-01` traces the key
resolution path used by connection test, startup connection check, AI analysis
generation, and runtime provider construction.

## Reproduced Symptom

After saving a valid OpenAI key and restarting, the app could show provider
connection failure even though AI analysis refresh later worked. That points to
resolver/source mismatch rather than a provider-wide outage.

## Root Cause

Connection-test/startup/generation/runtime paths did not all use one resolver
policy:

- UI connection checks used the UI/pending/stored/env path.
- Manual AI generation used a separate generation resolver.
- `AIEngineProvider._get_config_api_key` accepted provider names differently and
  previously preferred environment values before settings.
- A stale or mismatched source could therefore make the startup connection check
  fail while a later generation path found a usable key.

## Unified Resolver Policy

All UI-side external provider paths now go through
`MainWindow._resolve_ai_provider_secret`.

Resolution order:

1. non-masked UI input, when a caller explicitly allows UI input
2. pending verified key
3. persisted provider-specific secret
4. provider-specific environment fallback

Service runtime resolution in `AIEngineProvider._get_config_api_key` normalizes
`gpt/openai -> openai`, `gemini -> gemini`, and `local/basic -> local`, and reads
settings before environment fallback.

## Resolver Table

| Path | Caller | Normalized Provider | Resolver |
| --- | --- | --- | --- |
| OpenAI connection test | `_run_manual_ai_connection_check` | `openai` | `_resolve_ai_provider_secret` |
| Gemini connection test | `_run_manual_ai_connection_check` | `gemini` | `_resolve_ai_provider_secret` |
| startup connection check | `_run_ai_startup_connection_check_async` | `openai/gemini` | `_resolve_ai_provider_secret` |
| AI analysis refresh | `_resolve_ai_generation_secret` | `openai/gemini` | `_resolve_ai_provider_secret` |
| runtime service | `AIEngineProvider._get_config_api_key` | `openai/gemini/local` | settings-first service resolver |
| local provider | local/basic path | `local` | no external secret |

## Safe Diagnostics

Logs and reports may include:

- `key_present`
- `key_length`
- `key_fp`: first eight hex chars of `sha256(key)`
- key source name
- provider and caller

Logs and reports must not include:

- raw API key
- key prefix/suffix
- raw prompt
- raw provider payload

## Regression Proofs

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-bootstrap-trace --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-restart-regression-proof --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-bootstrap-trace --provider gemini --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-key-resolution-bootstrap-trace --provider local --observe-only
```

Expected safety flags:

- `key_fingerprints_match=true`
- `key_present_all_paths=true` for OpenAI/Gemini
- `local_secret_fallthrough=false`
- `provider_external_call_count=0`
- `order_risk_detected=false`

## Manual Verification

1. Select GPT/OpenAI.
2. Enter and save the OpenAI key.
3. Run connection check and confirm normal connection.
4. Restart the app.
5. Confirm GPT/OpenAI is restored.
6. Compare startup and generation key fingerprints in safe logs.
7. Run AI analysis refresh and confirm it uses the same key source/fingerprint.
8. Switch to Gemini and confirm OpenAI/Gemini key isolation remains intact.
