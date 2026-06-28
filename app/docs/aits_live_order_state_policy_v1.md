# AITS Live Order State Policy v1

## Purpose

This policy defines how AITS interprets exchange order state after a real order.
It is a read-only classification policy. It does not authorize another order,
cancel, sell, retry, unlock reuse, or live mode change.

AITS stores the exchange response as raw order data, then derives an AITS
normalized order state for logs, reports, reconciliation, and later operator
review. Raw exchange state must never be used alone to decide whether an order
failed or whether a new order may be attempted.

## Raw State And Normalized State

- `raw_state`: the exchange state returned by the order response or order query.
  Examples include `wait`, `done`, `cancel`, and query errors.
- `normalized_order_state`: the AITS interpretation after considering
  `executed_volume`, fees, locked amount, balance deltas, and query success.
- `reconciliation_status`: whether balances and order details have been
  compared enough to close the record for audit purposes.

The normalized state is descriptive only. It is not an order signal and it does
not unlock any follow-up order.

## First Live Order Case

The first AITS live order was a one-shot `KRW-BTC` market buy for `5000` KRW.

- order uuid: `06f08c3a-2bd3-4888-a7e6-2402623cb63e`
- initial raw state: `wait`
- later raw state: `cancel`
- executed_volume: `0.00005542`
- paid_fee: `2.49974681`
- locked: `0.50663319`
- KRW balance delta vs first post-order report: `0`
- BTC balance delta vs first post-order report: `0`
- reconciliation status: `reconciled`

This case is not treated as a simple failed or unfilled cancellation. Because
executed volume, paid fee, and BTC balance increase are present, AITS classifies
it as `partially_filled_cancelled_remainder`.

## Classification Rules

| Raw state | Evidence | Normalized order state | Required action |
| --- | --- | --- | --- |
| `wait` | `executed_volume == 0` | `submitted_waiting` | Do not retry. Do not cancel automatically. Query later only. |
| `wait` | `executed_volume > 0` | `partial_execution_waiting_remainder` | Do not retry. Do not cancel automatically. Reconcile later. |
| `done` | `executed_volume > 0` | `fully_filled` | Reconcile balances and fees. Do not retry. |
| `done` | `executed_volume == 0` | `unknown_requires_manual_review` | Stop and manually review exchange/account state. |
| `cancel` | `executed_volume > 0` | `partially_filled_cancelled_remainder` | Treat filled quantity as executed. Reconcile balances and fees. Do not retry. |
| `cancel` | `executed_volume == 0` | `cancelled_no_fill` | Treat as no-fill cancellation. Do not retry without a new explicit Goal. |
| query timeout or error | query failed | `query_failed_no_retry` | Do not retry the order. Query/read manually when safe. |
| any state | balance or fee mismatch | `unknown_requires_manual_review` | Stop. Do not order. Manual review required. |

Numeric comparisons should parse empty or missing `executed_volume` as unknown,
not as proof of zero, unless the exchange response explicitly reports zero.

## State-Specific Policy

### `submitted_waiting`

This means the exchange accepted the order and no fill has been observed yet.
AITS may perform read-only order lookup later. AITS must not submit another
order, cancel the order, or assume failure.

### `partial_execution_waiting_remainder`

This means some volume appears executed while the order is still waiting for the
remainder. AITS must not retry or cancel automatically. Later reconciliation
must compare fees, locked amount, and balances.

### `fully_filled`

This means the order is filled and should be closed by reconciliation. AITS must
record executed volume, fee, and balance changes. It must not trigger another
order from this state.

### `partially_filled_cancelled_remainder`

This is the normalized state for `raw_state=cancel` with executed volume greater
than zero. It means the filled portion counts as a real execution and only the
unfilled remainder appears cancelled or released by the exchange. AITS must
record the execution, paid fee, locked residual, and balances. It must not treat
the whole order as failed, and it must not retry.

### `cancelled_no_fill`

This means the order is cancelled and no execution is observed. It is still not
permission to retry. A new order requires a separate explicit Goal, new one-shot
unlock, fresh RiskGuard pass, fresh LiveOrderPreflight pass, duplicate-lock
clearance, and user approval.

### `query_failed_no_retry`

This means AITS could not safely determine the order state. The only allowed
next action is read-only inspection or manual exchange/account review. Retry,
cancel, sell, or additional buy attempts are prohibited.

### `unknown_requires_manual_review`

This means the raw state, execution fields, fees, locked amount, or balances do
not form a coherent record. AITS must stop live-order progression until a human
operator reconciles the exchange and account state.

## Balance Reconciliation Requirements

A reconciled order record should include:

- order uuid
- raw state
- normalized order state
- market, side, order type, and requested price or amount
- executed volume
- remaining volume when available
- paid fee, reserved fee, remaining fee, and locked amount when available
- KRW balance
- asset balance for the traded symbol
- delta vs the first post-order report when available
- relock state
- duplicate-lock state
- repeat-order blocked proof

If balances disagree with executed volume or fee beyond known exchange rounding
behavior, classify the order as `unknown_requires_manual_review`.

## No-Retry Principle

All normalized states preserve the no-retry rule. AITS must not place a new
order because a previous order is waiting, cancelled, partially filled, failed
to query, or unclear. Another live order requires a new Goal and a fresh
authorization chain.

## Next Live Order Requirement

Before another real order, AITS must:

- keep the previous order classified and reconciled
- prove relock and duplicate-lock persistence after restart
- prove post-order read-only reconciliation still works
- require a new explicit Goal and user confirmation phrase
- run fresh RiskGuard, LiveOrderPreflight, and One-Shot Unlock checks
