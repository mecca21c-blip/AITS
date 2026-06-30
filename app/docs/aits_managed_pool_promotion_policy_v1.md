# AITS Managed Pool Promotion Policy v1

Purpose: define Basic candidate promotion, removal protection, and rotation
intent planning without executing trades.

## Scope

This policy is planning only. It may produce `planned_add`, `planned_remove`,
and `planned_rotation`, but it must not mutate user Managed Pool rows or call
buy, sell, cancel, retry, RiskGuard, Preflight, OrderAdapter, OrderService, or
ExecutionBridge.

Actual Managed Pool mutation requires a later explicit apply Goal. Actual
orders require a separate live-execution Goal.

## Config

- `max_managed_pool_size`: user setting, default `10`
- `promotion_min_score`: `None`
- `auto_add_enabled`: `True`
- `auto_remove_enabled`: `True`
- `protect_user_added`: `True`
- `protect_holdings_until_liquidated`: `True`
- `protect_system_seed_initially`: `True`
- `rotation_enabled`: `True`
- `rotation_min_score_gap`: `0.0`
- `order_execution_enabled`: `False`

Initial operation is rank-relative. Fixed score thresholds are intentionally
left unset until more runtime data exists.

The max size is no longer a hard-coded policy value. The Managed Pool footer
owns the user-facing setting (`ui_state.managed_pool_max_size`) with default
`10`, minimum `1`, and maximum `50`. Policy callers must pass this value into
`ManagedPoolPromotionConfig`; `10` is only the fallback default when the setting
is absent or invalid.

## Source Types

- `user_added`: user-managed row, never auto-removed.
- `basic_added`: Basic auto-promotion row, removable when rank/score falls.
- `system_seed`: initial seed rows such as `KRW-BTC`, `KRW-ETH`, `KRW-XRP`,
  protected in the initial policy.
- `holding`: live holding, protected until liquidation is confirmed.

## Promotion

When the pool has fewer rows than the configured max, Basic top candidates not
already managed can be planned for addition in rank order. Planned rows use
`source_type=basic_added` and include score, rank, reason, trade value, and
`actual_order=false`.

The first actual apply path is add-only: it may persist `planned_add` rows up to
the configured max, but it must not execute `planned_remove`, rotation, orders,
sell, cancel, or retry.

Changing `max_managed_pool_size` only saves the setting. It does not add or trim
rows by itself. The Managed Pool footer has a separate `바로적용` button that
synchronizes rows to the current max size:

- current count > max: remove only unprotected `basic_added` rows.
- current count < max: run the Basic candidate scan and add top candidates as
  `basic_added` rows up to the max.
- current count == max: no-op.

The button never calls any order path or executes rotation.

## Removal

Only non-protected `basic_added` rows are removable. `user_added`,
`holding`, `manual_hold`, and protected `system_seed` rows are not removal
targets. If the pool is full, a higher-ranked new candidate may create a
replacement plan against the weakest removable `basic_added` row.

The max-size apply trim uses this priority for removable `basic_added` rows:
lowest score first, then worse rank, then older `added_at`, then symbol for
determinism. If protected rows make it impossible to reach the configured max,
the plan reports `protected_overflow=true` and keeps protected rows.

## Rotation

Rotation is opportunity-cost detection, not execution. If a new candidate score
is higher than a holding score, the plan may emit:

- `rotate_out`
- `rotate_in`
- `sell_candidate=true`
- `buy_candidate=true`
- `actual_order=false`

Example: holding score 60 and candidate score 70 produces a rotation pair, but
the holding remains in Managed Pool until liquidation is confirmed.

Rotation intent can be normalized into `aits_rotation_intent_v1` for UI and
runtime proof. The intent payload is explanatory only: it may produce `교체 검토`
or `진입 후보` status hints and tooltip text, but it must keep
`actual_order=false`, `order_execution=false`, `rotation_execution=false`, and
`managed_pool_mutation=false`.

## Proof

Use:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-promotion-policy-proof --max-managed 10 --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-auto-promotion-apply-proof --max-managed 10 --apply-add-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-proof --from-max 10 --to-max 8
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-actual-proof --to-max 8 --apply-trim
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-sync-proof --from-count 8 --to-max 10
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-sync-actual-proof --to-max 10 --apply-sync
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-intent-ux-proof --fixture score-gap
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode rotation-intent-live-candidate-proof --observe-only
```

The proof covers auto-add, user protection, holding protection, max-10
enforcement, low-rank `basic_added` removal candidates, rotation pair creation,
no-rotation when candidate score is lower, and duplicate candidate ignoring.
The apply-button proof covers both sync branches: increasing max adds Basic
candidates, decreasing max trims only unprotected `basic_added` rows, equal
counts no-op, and protected rows are preserved.

## Explainable Sync UX

Every max-size sync apply produces a JSON-safe `managed_pool_sync_explain_v1`
payload. The same payload drives the popup message, the Managed Pool footer
summary, the harness report, and one `[AITS][ManagedPoolSyncExplain]` log line.

The payload records:

- `added`: symbol, score, rank, source, and add reason.
- `removed`: symbol, score, rank, source, and trim reason.
- `protected`: symbol and protection reason such as `user_added`,
  `trade_hold`, `holding_until_liquidated`, or `system_seed`.
- `skipped`: no-candidate or no-op explanation.
- `message`, `summary`, and `detail` for user-facing display.

This UX layer is explanatory only. It does not change promotion, trim,
rotation, or order-execution policy.
