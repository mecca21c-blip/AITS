# AITS Provider Settings Runtime SSOT v1

## Goal

`AITS-AI-PROVIDER-SETTINGS-RUNTIME-SSOT-ROOT-FIX-01` fixes the provider
settings lifecycle so saved provider choice, provider-specific key/model
settings, runtime provider injection, and UI connection state use one active
path.

## Provider SSOT

- Saved strategy SSOT: `strategy.ai_provider`
- Internal saved values: `openai`, `gemini`, `local`
- UI/session provider values: `gpt`, `gemini`, `basic`
- Runtime service values: `openai`, `gemini`, `local`

Normalization is centralized through the app provider normalizers:

- `GPT`, `gpt`, `OpenAI`, `openai`, `chatgpt` -> saved `openai`, UI `gpt`
- `Gemini`, `gemini` -> saved/UI `gemini`
- `Local`, `local`, `basic` -> saved `local`, UI `basic`

## Key And Model Storage Map

- OpenAI key: provider-specific OpenAI secret path only.
- Gemini key: provider-specific Gemini secret path only.
- Local: no external API key.
- OpenAI model: `strategy.ai_openai_model`
- Gemini model: `strategy.ai_gemini_model`
- Local model: `strategy.ai_local_model`

OpenAI and Gemini keys must never share a storage key. Local/basic paths must
not read Gemini or OpenAI secrets as a fallback.

## Lifecycle

Startup:

1. Load prefs/settings.
2. Validate settings schema.
3. Normalize `strategy.ai_provider`.
4. Resolve provider-specific key/model.
5. Reflect settings in UI controls.
6. Apply selected provider to runtime preview/session.
7. Initialize selected-provider connection snapshot.
8. Render `check needed`, `connecting`, `connected`, or `failed` from the
   provider connection snapshot.

Provider change:

1. Normalize UI provider value.
2. Update session selected provider.
3. Resolve only that provider's key/model.
4. Invalidate only that provider's connection snapshot.
5. Render selected provider status.

Key save:

1. Store the key in the provider-specific secret path.
2. Keep only masked/key-present status in diagnostics.
3. Sync selected provider runtime after save.
4. Clear stale failure reason for the selected provider.
5. Let the next real connection check write `connected` or `failed`.

Manual AI refresh:

1. Uses the selected provider runtime snapshot.
2. Updates AI generation/freshness state.
3. Does not downgrade provider connection status because generation is stale,
   missing, or not confirmed.

## Cross-Provider Isolation

Provider connection snapshots are selected-provider scoped. An OpenAI failure
must not appear while Gemini is selected, and a Gemini failure must not overwrite
OpenAI. Switching back to a provider may restore that provider's own cached
connection snapshot, but not another provider's result.

## Logging

Provider lifecycle diagnostics use these prefixes:

- `[AITS][ProviderSSOT]`
- `[AITS][ProviderSettings]`
- `[AITS][ProviderRuntimeSync]`
- `[AITS][EngineStatusWriter]`

Allowed diagnostic data: provider names, storage key names, model key names,
masked/key-present booleans, previous/next status, source path, and stale
snapshot invalidation flags.

Forbidden diagnostic data: API key body, provider secret fragments, raw prompts,
raw provider payloads, and raw provider responses.

## Regression Proofs

```powershell
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-settings-runtime-ssot-diagnostic --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-settings-restart-restore-regression-proof --provider gpt --observe-only
.\.venv\Scripts\python.exe tools\runtime_smoke\aits_qt_smoke_harness.py --mode provider-switching-cross-provider-regression-proof --observe-only
```

The default proofs use mock/simulated provider state and must keep
`provider_external_call_count=0`.
