# AITS LivePreflight Read-Only Adapter Contract v1

## Goal

`aits_live_preflight_readonly_adapter_contract_v1` defines the design boundary
between the current LivePreflight readiness stub and any future adapter that can
inspect the real LivePreflight input/output shape.

This is a design contract only. It does not call LivePreflight, does not execute
or consume a one-shot unlock, does not emit an order intent, and does not call
DecisionRouter, RiskGuard, ExecutionBridge, OrderService, or OrderAdapter.

## Current Stub Chain

The current no-call order-intent readiness chain is:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy readiness
5. Router validation payload readiness
6. One-shot unlock readiness stub
7. LivePreflight readiness stub

Each step produces a report payload and keeps execution-side flags false. The
last completed stub is `aits_order_intent_live_preflight_readiness_v1`, which
can report `live_preflight_readiness=true` for a mock-approved 10,000 KRW
candidate while still keeping `live_preflight_called=false` and
`actual_order_intent_emitted=false`.

## Adapter Purpose

The future read-only adapter may translate a readiness payload into the shape
that real LivePreflight would later need. It must remain an adapter contract,
not a service invocation.

Allowed responsibilities:

- normalize candidate fields for a future LivePreflight request
- verify that required fields are present
- report missing fields, policy blockers, and warnings
- prove that the adapter can remain disconnected from order execution

Forbidden responsibilities:

- call `LivePreflight`
- call RiskGuard
- call DecisionRouter
- call ExecutionBridge
- call OrderService or OrderAdapter
- execute or consume a one-shot unlock
- emit an actual order intent
- place, cancel, sell, retry, or submit an order

## Input Schema

The adapter input should be named
`aits_live_preflight_readonly_adapter_input_v1`.

Required fields:

- `schema`
- `symbol`
- `side`
- `intended_amount_krw`
- `source`
- `candidate_schema`
- `source_policy_ready`
- `router_validation_payload_ready`
- `one_shot_unlock_ready`
- `live_order_readiness`
- `live_preflight_readiness`
- `min_order_krw`
- `per_order_hard_cap_krw`
- `total_window_cap_krw`
- `total_window_after_candidate_krw`
- `duplicate_guard_required`
- `repeat_guard_required`
- `relock_required`
- `submitted_count`
- `actual_order=false`
- `validation_only=true`

The input must not include API keys, raw provider payloads, raw exchange
responses, or any executable callback.

## Output Schema

The adapter output should be named
`aits_live_preflight_readonly_adapter_contract_v1`.

Required fields:

- `schema`
- `symbol`
- `side`
- `adapter_ready`
- `adapter_mode=readonly_contract`
- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `order_service_reachable=false`
- `order_adapter_reachable=false`
- `risk_guard_called=false`
- `decision_router_called=false`
- `unlock_consumed=false`
- `actual_order_intent_emitted=false`
- `actual_order=false`
- `submitted=0`
- `blockers`
- `warnings`
- `required_next_goal`

`adapter_ready=true` means only that the read-only adapter contract has enough
data to build a future LivePreflight request preview. It is not permission to
call LivePreflight, consume unlock, emit an intent, or submit an order.

## Call Boundaries

The adapter must be hard-wired to report:

- `would_call_live_preflight=false`
- `live_preflight_called=false`
- `unlock_consumed=false`
- `order_service_reachable=false`
- `order_adapter_reachable=false`
- `actual_order=false`
- `submitted=0`

Any implementation that needs a real service instance, exchange credential,
network call, unlock consumption, or OrderService reachability belongs in a
separate high-risk Goal.

## Unlock Readiness vs Consume

One-shot unlock readiness and unlock consumption are separate states:

- readiness proves that an exact symbol/amount/session approval would be
  acceptable
- consumption must happen only at the final execution boundary

The current stub may use mock unlock approval to prove readiness. A future
read-only adapter may carry `one_shot_unlock_ready=true`, but it must still keep
`unlock_consumed=false`. Consuming unlock before the final execution boundary is
forbidden because it can create a stale, spent, or misleading order state.

## RiskGuard and LivePreflight Sequence

The final live-order sequence should be:

1. Basic Buy Ready
2. Fresh AI Opinion
3. Inert order intent candidate
4. Source live policy
5. Router validation payload
6. RiskGuard read-only validation
7. LivePreflight read-only validation
8. One-shot unlock confirmation
9. Duplicate/repeat/relock final check
10. ExecutionBridge
11. OrderService
12. OrderAdapter
13. Exchange response reconciliation

The previous stub chain checks one-shot unlock readiness before LivePreflight
readiness because both are inert proof payloads. The actual live sequence must
not consume unlock until after Router, RiskGuard, and LivePreflight validations
are fresh and the final duplicate/repeat/relock checks still pass.

## Risk Register

- A read-only adapter accidentally imports and calls the real LivePreflight
  service.
- Unlock readiness is treated as unlock consumption.
- `live_preflight_readiness=true` is misunderstood as order permission.
- Router validation stub is confused with an actual DecisionRouter call.
- LivePreflight is reached before a fresh RiskGuard validation exists.
- `submitted_count` is stale and does not reflect a previous order attempt.
- Duplicate, repeat, or relock checks are skipped or run before the final
  execution boundary.
- OrderService or OrderAdapter becomes reachable from a validation-only path.

## Next Implementation Goal

The next implementation should be limited to:

`AITS-LIVE-PREFLIGHT-READONLY-ADAPTER-SKELETON-PROOF-01`

That Goal may add a skeleton adapter and proof payload, but it must still keep
`would_call_live_preflight=false`, `live_preflight_called=false`,
`unlock_consumed=false`, `actual_order_intent_emitted=false`,
`actual_order=false`, and `submitted=0`.
