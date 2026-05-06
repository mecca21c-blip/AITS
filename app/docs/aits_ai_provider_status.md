# AITS AI Provider Status

## 103-120 Summary

- AITS persisted settings are loaded during bootstrap and passed into the orchestrator/provider context.
- AI provider diagnostics now expose provider selection, key resolution source, and safe call-gate state without printing secrets.
- Provider labels are normalized to `basic`, `openai`, and `gemini`; internal `local` behavior remains an alias for `basic`.
- AI verification results are stored as suggestion-only metadata and history records.
- DecisionRouter logs AI suggestion receipt, storage, history stats, compact stats, and RouterSummary AI counters without changing final actions.
- Verbose AI stats logs remain enabled by default and can be disabled with `AITS_AI_STATS_VERBOSE=0`.

## Providers

- `basic`: local/basic path, no external API call required.
- `openai`: OpenAI provider path, gated before any real request.
- `gemini`: Gemini provider path, gated before any real request.

## Key Resolver

Key resolution is reported only as a state and method:

- `environment`: key found through environment fallback.
- `settings`: key found through persisted settings/app state/config fallback.
- `missing`: no key found.

No API key, payload, prefix, length, or settings dump is written to logs or docs.

## Real Call Gate

Real AI calls are off by default. Both environment flags must be set for the real-call gate to report enabled:

```text
AITS_ENABLE_REAL_AI_CALL=1
AITS_REAL_AI_ONE_SHOT=1
```

If either value is absent, the provider remains in dry-run/safe skip behavior.

## Suggestion-Only Contract

AI verification output is treated as metadata only:

```text
suggestion_only=True
applied_to_action=False
```

DecisionRouter keeps final action passthrough behavior and does not use AI suggestions to create or modify orders.

## RouterSummary Fields

RouterSummary includes AI suggestion counters:

- `ai_t`: total AI suggestion records in the stats window.
- `ai_c`: confirm count.
- `ai_s`: skip count.
- `ai_r`: reject count.
- `ai_a`: applied count, fixed at `0`.

Detailed AI stats logs are still available unless `AITS_AI_STATS_VERBOSE=0`.

## Safety State

- OrderAdapter mode remains `disabled`.
- `submitted=0` is maintained.
- No buy order request is emitted.
- No sell order request is emitted.
- Real trading execution mode was not changed.

## Next Step

Before a one-shot real API smoke test:

- Confirm provider selection in the UI.
- Confirm key resolution reports `environment` or `settings` without exposing the key.
- Confirm both real-call gate flags are intentionally set.
- Confirm OrderAdapter remains disabled and submitted count remains zero.
