# AITS Provider Runtime Contract Context Audit v1

## 1. Audit Summary

The PID 18332 portfolio redecision completed successfully, but its provider request log reported
`runtime_contract_active=false` and `execution_mode=-`. The runtime heartbeat, scheduler,
decision registration, and ETA state all remained active and canonical. The root cause was missing
request metadata: the portfolio payload did not carry the runtime contract snapshot consumed by
`AIEngineProvider`.

The mismatch is classified as a metadata propagation mismatch with a logging-only symptom. It was
not an actual runtime contract transition and did not alter AI actions or order controls.

## 2. Runtime Session

- Git head: `75924923`
- Runtime PID: `18332`
- Session: `on-18332-1783943720`
- ON start: `2026-07-13 20:55:16 KST`
- Portfolio redecision: `2026-07-13 21:55:57 KST`
- Registration: `PORTFOLIO`, `portfolio_management_decision`, `portfolio:PORTFOLIO`
- Actual orders: 0

## 3. Observed Mismatch

| source | runtime_contract_active | execution_mode | session_id | scope | task | evidence | note |
|---|---|---|---|---|---|---|---|
| runtime heartbeat | true | live | ON session | runtime | heartbeat | RuntimeContract | Runtime SSOT active |
| runtime contract snapshot | true | live | on-18332-1783943720 | runtime | scheduler | ETA scheduler probe | ReDecision allowed |
| provider request log | false | `-` | missing | PORTFOLIO | ai_redecision | AIEngineProvider request | Request metadata absent |
| payload quality log | n/a | n/a | scoped log session | PORTFOLIO | ai_redecision | grade A, 21/22 | Payload quality unaffected |
| decision registration log | n/a | n/a | scoped log session | portfolio_management | portfolio_management_decision | state readback confirmed | Canonical registration |
| training record | n/a | n/a | missing historically | PORTFOLIO | portfolio management | redecision record | Scope canonical; session metadata added by fix |
| harness summary | true | live runtime | on-18332-1783943720 | PORTFOLIO | canonical registration | target PID/session scope | Parser scope clean |

## 4. Provider Context Source

Before this audit, `AIEngineProvider` derived its log fields only from top-level
`runtime_contract_active` or `current_policy.execution_mode`. Position payloads commonly carried
the latter, while the portfolio payload builder carried neither. Python boolean coercion converted
missing context to `false`, and the absent execution mode was rendered as `-`.

Provider logging now distinguishes `true`, `false`, and `unknown`. It records `session_id` and
`context_source` without inspecting UI state or guessing runtime state.

## 5. Runtime SSOT Source

The GUI callsite creates a request snapshot from `_aits_runtime_contract_state`, falling back to
the existing `_aits_runtime_contract_active` attribute only when the state dictionary has no active
field. Execution mode comes from `_get_aits_execution_mode`; the ON session comes from the active
initial seed session identifier. This is a request snapshot, not a new SSOT.

## 6. Payload / State / Training Record Comparison

The portfolio redecision payload, validator result, runtime registration, ETA state, and training
record remained internally consistent, but the historical training row omitted its session ID.
The fix attaches the same runtime snapshot to initial and redecision management payloads and stores
a safe context summary so provider logs and training provenance can be audited against the runtime
session.

## 7. Mismatch Classification

| mismatch_type | detected | evidence | severity | recommended_action |
|---|---|---|---|---|
| logging-only mismatch | true | false/default values appeared only in provider logs | low | Preserve unknown explicitly |
| metadata propagation mismatch | true | portfolio payload lacked runtime metadata | medium | Attach upstream runtime snapshot |
| parser scope mismatch | false | PID 18332/session scope was selected | none | Keep target PID/session filtering |
| actual runtime contract mismatch | false | heartbeat, scheduler, registration remained active | none | No runtime policy change |

## 8. Risk Assessment

The defect could mislead incident analysis and provider audit reports. It did not bypass provider
policy, Router, RiskGuard, LivePreflight, Execution, or order submission. No action or strategy
logic is changed by the context alignment.

## 9. Fix Recommendation

- Pass runtime contract metadata from the callsite; never infer or hardcode it in the provider.
- Render absent boolean metadata as `unknown`, not `false`.
- Log the context source and ON session identifier.
- Compare only provider logs within the selected running PID/session.
- Keep provider context mismatch separate from order and action decisions.

## 10. Next Goal

Run a fresh ON-session verification and confirm `ProviderRuntimeContext event=context_collected`,
`runtime_contract_active=true`, `execution_mode=live`, and the matching session identifier for a
portfolio redecision.
