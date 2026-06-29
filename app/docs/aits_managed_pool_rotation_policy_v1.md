# AITS Managed Pool Rotation Policy v1

Purpose: separate observe-only candidate/rotation proof from actual Managed
Pool mutation.

## Mutation Boundary

The following fields are proof-only:

- `would_add`
- `would_keep`
- `would_remove`
- `would_rotate`

They must not append, delete, replace, sell, cancel, retry, or submit orders.
Actual Managed Pool mutation requires a separate Goal and explicit user approval.
User-added rows and holding-derived rows must not be removed by observe-only
proof.

## Managed Pool Reflection

Current Managed Pool state is read from `ai_managed_rows` and persisted snapshots
under `managed_pool_rows`. Existing rows can receive market field and Basic score
updates, but observe-only proof must keep the symbol set unchanged.

## Rotation Path

Rotation soft signal ownership is split:

- `app/services/basic_decision_engine.py` builds Basic `rotation` payloads.
- `MainWindow._aits_last_rotation_payload` carries the latest soft payload.
- `MainWindow._get_aits_rotation_soft_weights` and managed-pool context builders
  expose the signal to analysis context.

Rotation is a review signal only. It is not an execution command and does not
authorize sell, buy, cancel, retry, or row deletion.

## No-Rotation Reasons

Observe-only reports should use explicit reasons:

- `no_candidates_for_rotation`
- `rotation_soft_payload_empty`
- `top_markets_empty`
- `market_rows_empty`

If the market candidate feed is empty, rotation cannot be evaluated beyond
confirming that no soft rotation payload is active.

## Feed Dependency

Rotation observe-only proof depends on Basic top-market candidates. Use
`top-markets-feed-proof` first when reports show `top_markets_empty`; a healthy
feed should provide nonzero KRW market and top-market counts before rotation
absence is interpreted as a strategy condition.
