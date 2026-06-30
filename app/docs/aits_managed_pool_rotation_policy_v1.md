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
- `no_holding_rows_for_rotation`
- `no_higher_score_candidate`
- `all_candidates_already_managed`
- `score_gap_not_met`
- `protected_rows_only`
- `holding_dust_filtered`
- `managed_row_holding_flag_missing`

If the market candidate feed is empty, rotation cannot be evaluated beyond
confirming that no soft rotation payload is active.

## Holding Eligibility

Rotation pairs require a holding-eligible row. The holdings proof reads Upbit
balances through the existing read-only holdings path and treats positions
below `5000 KRW` evaluated value as dust for rotation eligibility. Dust
holdings may still appear in `would_mark_holding`, but they do not become
`rotate_out` candidates until a later Goal changes the minimum-value policy.

Holding display and holding eligibility are separate policy states:

- `holding_display=true`: a balance exists and the row may be shown as held,
  including dust balances below `5000 KRW`.
- `holding_eligible=true`: the evaluated value is at or above `5000 KRW` and
  the holding may participate in rotation intent calculation.
- Dust holdings are display-only. They should be described as `소액 보유` /
  operation-excluded in tooltip or report payloads, are not auto-deleted, and
  are not rotation candidates.
- The live-trading minimum test amount remains `10000 KRW`; that is separate
  from the `5000 KRW` dust-display threshold.

Managed Pool UI may apply a read-only holding-display overlay during row
rendering. When a saved Managed Pool symbol matches a live dust balance, the
row can show small-holding status and a tooltip explaining the value, dust
threshold, and rotation exclusion. This overlay must not persist row changes,
must not promote holdings outside the Managed Pool, and must not mark dust as
`holding_eligible`.

`holdings-to-managed-row-proof --observe-only` reports current holdings,
Managed Pool matches, missing holding flags, `would_display_holding`,
`would_mark_holding_eligible`, and tooltip samples without persisting row
changes. `rotation-eligibility-from-holdings-proof --observe-only` then uses
only observed eligible holdings in memory to verify whether rotation intent can
be calculated. If all observed holdings are dust, the expected reason is
`holding_dust_filtered`.

`managed-pool-holding-display-sync-proof --observe-only` verifies the UI
overlay policy: matched rows such as KRW-BTC may receive display-only holding
status and tooltip samples, while outside holdings are reported but not added.

## Feed Dependency

Rotation observe-only proof depends on Basic top-market candidates. Use
`top-markets-feed-proof` first when reports show `top_markets_empty`; a healthy
feed should provide nonzero KRW market and top-market counts before rotation
absence is interpreted as a strategy condition.

`rotation-intent-live-candidate-feed-proof --observe-only` is the public-feed
rotation proof for that healthy-feed case. It allows only Upbit public
market/ticker GET reads, keeps provider POST and order/private paths blocked,
reads saved Managed Pool rows without mutation, and reports `pair_count` or a
strategy/position reason such as `no_holding_rows_for_rotation` instead of
`top_markets_empty`.

## Promotion Policy Integration

`managed_pool_promotion_policy.py` may emit rotation pairs when a new Basic
candidate score is above a holding score. A pair marks the holding as
`rotate_out` / `sell_candidate` and the new symbol as `rotate_in` /
`buy_candidate`, but `actual_order=false` is mandatory. The holding remains in
Managed Pool until liquidation is confirmed by a later live execution and
reconciliation Goal.

## Rotation Intent UX

Rotation intent uses the JSON-safe `aits_rotation_intent_v1` schema. It records
observe-only `pairs` with `rotate_out_symbol`, `rotate_out_score`,
`rotate_in_symbol`, `rotate_in_score`, `score_gap`, `reason_text`,
`actual_order=false`, `order_execution=false`, `rotation_execution=false`, and
`managed_pool_mutation=false`.

The Managed Pool table may show a short status hint such as `교체 검토` or
`진입 후보`; the full reason belongs in the hover tooltip. Tooltip text should
explain the peer symbol, score gap, opportunity-cost reason, and that no order
is executed.

Use:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-intent-ux-proof --fixture score-gap
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-intent-live-candidate-proof --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-intent-live-candidate-feed-proof --observe-only --max-candidates 50
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode holdings-to-managed-row-proof --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-eligibility-from-holdings-proof --observe-only
```

The fixture proof must create the 60 score versus 70 score pair. The live
candidate proof may report `pair_count=0` when the current candidate feed has no
higher-scoring candidate; in that case `no_rotation_reason` must be explicit.
