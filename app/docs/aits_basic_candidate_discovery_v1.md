# AITS Basic Candidate Discovery v1

Purpose: document the active Basic Engine candidate discovery path and its
observe-only proof boundary.

## Active Owners

- Market/top candidate feed owner: `MainWindow._load_market_explorer_initial_data`
- Basic score owner: `MainWindow._calc_basic_ai_score`
- Candidate feed health owner: `MainWindow._mark_candidate_feed_state`
- Managed row score/status sync owner: `MainWindow._update_ai_pool_statuses`
- AI review queue owner: `MainWindow._build_managed_pool_ai_review_queue`

The observed trigger path loads top KRW markets, copies market fields into
current managed rows, recalculates Basic scores, refreshes the managed table,
and builds the review queue. This is calculation/reference behavior and is not
an order signal.

## Input Data

The scan depends on:

- `get_top_markets_by_volume(limit=30)`
- public Upbit market list and ticker reads
- `market_all_rows`
- `_market_display_rows`
- current `ai_managed_rows`
- optional holding rows for review priority

If top market data is empty, candidate discovery must report a concrete
`no_candidate_reason`, such as `top_markets_empty` or `market_rows_empty`.
The companion `top-markets-feed-proof` report separates public feed failures
from Basic scoring filters by recording `market_count_raw`,
`krw_market_count`, `ticker_count`, `top_markets_count`, and `empty_reason`.

## Output Schema

Observe-only reports use:

- `candidate_count`
- `top_candidates`
- `symbol`
- `rank`
- `score`
- `reason`
- `source`
- `change_rate`
- `trade_value`
- `no_candidate_reason`

When candidates exist, the top rows are ranked by Basic score and trade value.
When no candidates exist, the reason is the important proof result.

## Current Proof Result

`basic-candidate-discovery-proof` on 2026-06-29 observed:

- Basic scan owner existed and was called.
- Scan completed successfully.
- `market_count=0`
- `top_markets_count=0`
- `candidate_count=0`
- `no_candidate_reason=top_markets_empty`
- Managed Pool remained unchanged: `KRW-BTC`, `KRW-ETH`, `KRW-XRP`
- Provider external calls: `0`
- Order calls: `0`

Interpretation: the Basic scoring/review path is present, but new market
candidate discovery had no input rows. The next fix should focus on why
`get_top_markets_by_volume` / ticker feed returns empty in the active runtime.

## Top Markets Feed Proof

`top-markets-feed-proof` is the read-only proof for this input layer. It may
read public Upbit market/ticker endpoints, but it must not call provider APIs,
account/order APIs, change Managed Pool rows, or create order activity.

Expected healthy input proof:

- `krw_market_count > 0`
- `ticker_count > 0`
- `top_markets_count > 0`
- `empty_reason=""`

If candidates are still zero after top markets are present, the reason should
move from `top_markets_empty` to a scoring/filter reason, such as symbols
already managed or Basic thresholds not met.

## Promotion Boundary

Basic candidate promotion is defined in
`app/services/managed_pool_promotion_policy.py`. The current policy is
rank-based with no fixed score threshold. `max_managed_pool_size` comes from
the user setting in `ui_state.managed_pool_max_size`; `10` is only the default
fallback. The Basic scan may feed top candidates into the promotion policy.

`managed-pool-auto-promotion-apply-proof --apply-add-only` is the first actual
mutation proof. It may add `basic_added` rows up to the configured max, but it
must not remove rows, execute rotation, call providers, or create orders.

Changing the max size is intentionally not automatic. The Managed Pool footer
`바로적용` button owns max-size sync. If the pool is below the max, it runs the
Basic candidate scan and add-only promotion path. If the pool is above the max,
it removes only unprotected `basic_added` rows. User-added, trade-hold, holding,
and protected seed rows are preserved. If protected rows exceed the configured
max, the trim reports `protected_overflow` instead of deleting protected rows.

## Explainable Apply Result

When the max-size `바로적용` button adds Basic candidates, the UI and harness now
show why each symbol was selected. The explain payload includes Basic score,
rank, source, and selection reason. If no candidates are available, the payload
uses the no-candidate reason instead of reporting a silent no-op.

This keeps candidate discovery observable without presenting Basic calculation
output as an order signal.
