# AITS Runtime Smoke Harness v1

## Purpose

### LOCAL Model Calibration Data Accumulation v1

`--mode local-model-calibration-data-accumulation-v1-summary --observe-only`
combines one running non-harness ON session with persisted outcome, curated,
feature, training, LOCAL_MODEL, calibration, and order-reconciliation evidence.
It requires at least 120 minutes of observed session time and at least one real
checkpoint result. It does not start AITS, call a provider, place an order, or
manufacture missing pipeline data. `no_data` and `insufficient_data` remain
truthful model states; reconciliation misses and guard bypasses are blockers.

The Qt smoke harness provides a screenshot-free way to inspect the live AITS
widget tree when Windows screenshot capture or Computer Use click automation is
unavailable.

It is a test infrastructure tool only. It must not run during normal
production startup.

## Entry Point

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-read
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-navigation
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode engine-connection-status-path-diagnostic --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode engine-connection-status-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode engine-connection-key-refresh-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-settings-runtime-ssot-diagnostic --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-settings-restart-restore-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-switching-cross-provider-regression-proof --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-key-resolution-bootstrap-trace --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-key-resolution-restart-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-connection-log-forensic-summary --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-readiness-source-summary --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-readiness-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-ready-snapshot-summary --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-provider-ready-regression-proof --provider gpt --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-button-state-trace-dryrun --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-button-state-log-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-setting-source-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode save-probe
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode top-markets-feed-proof --max-markets 20
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode basic-candidate-discovery-proof --observe-only --max-candidates 10
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-promotion-policy-proof --max-managed 10 --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-promotion-quality-gate-proof --max-managed 10 --min-score 60
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-promotion-quality-live-proof --observe-only --max-managed 10 --min-score 60
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-quality-ranked-rebuild-proof --max-managed 10 --min-score 60
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-quality-ranked-rebuild-live-proof --observe-only --max-managed 10 --min-score 60
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-ui-apply-proof --observe-only --provider local --target-symbol KRW-BTC
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-ui-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-auto-promotion-apply-proof --max-managed 10 --apply-add-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-proof --from-max 10 --to-max 8
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-actual-proof --to-max 8 --apply-trim
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-sync-proof --from-count 8 --to-max 10
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-max-size-apply-button-sync-actual-proof --to-max 10 --apply-sync
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimum-real-order-test --confirm-phrase <exact-confirm-phrase>
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-order-post-trade-reconciliation --order-uuid <order-uuid>
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-preflight-proof --duration-min 120 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window-order-path-cap-proof --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-2h-guarded-window --confirm-phrase AITS_LIVE_2H_GUARDED_WINDOW_KRW_BTC_10000_MAX2_CONFIRM --duration-min 1 --per-order-krw 10000 --per-order-hard-cap-krw 12000 --total-window-cap-krw 20000 --max-order-count 2 --min-order-interval-sec 600 --dry-run-no-on
```

Reports are written to:

```text
data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json
```

Reports are UTF-8 JSON without a BOM. The harness normalizes report values to
JSON-safe primitives before writing: strings keep Korean and UI symbols, unsafe
control characters and invalid surrogate code points are replaced or removed,
paths are stored as strings, non-finite floats become `null`, and unknown
objects are reduced to safe `repr(...)` text. The same sanitized report is
printed to stdout.

Dry-read reports also record the global Qt tooltip readability style proof:
`tooltip_stylesheet_present`, `tooltip_background`, `tooltip_color`,
`tooltip_border`, and `tooltip_padding`. This is UI polish only; tooltip content,
Managed Pool rows, provider calls, and order state are unchanged.
Managed Pool tooltip samples include an escaped HTML light-card fallback through
`tooltip_html_sample` and `tooltip_html_card_supported`, because some OS/remote
runtime environments ignore native `QToolTip` background styling.

## Modes

- `dry-read`: creates the real Qt main window in a guarded harness process,
  reads objectName/property selectors, label text, row counts, latest trade-log
  row text, and safety state. It does not click buttons.

- `live-on-preflight-provider-readiness-source-summary`: reports the active
  ON preflight provider readiness owner and confirms it reads the provider
  connection snapshot instead of AI analysis freshness or UI label text.
- `live-on-preflight-provider-readiness-regression-proof`: mock-only proof that
  GPT/Gemini connection readiness is not downgraded by stale or missing AI
  generation freshness. The mode keeps `provider_external_call_count=0` and
  `submitted_count=0`.
- `live-on-preflight-provider-ready-snapshot-summary`: alias for the ON
  preflight provider-ready snapshot report. It exposes connection snapshot
  source, key fingerprint, and generation success evidence without logging key
  material.
- `live-on-preflight-provider-ready-regression-proof`: mock-only proof that a
  fresh confirmed GPT/Gemini generation with the same provider key fingerprint
  can satisfy ON preflight provider readiness when the connection snapshot is
  otherwise check-needed. Stale freshness, cross-provider snapshots, missing
  keys, and key fingerprint mismatches still block readiness.
- `dry-navigation`: performs the same read and switches tabs through the bottom
  navigation selectors. It does not click `AI 분석 새로고침`.
- `engine-connection-status-path-diagnostic`: inspects the provider connection
  status owner path without GPT/Gemini calls. It verifies that startup,
  provider-change, ON/runtime, and manual connection checks share
  `MainWindow._run_ai_startup_connection_check_async`,
  `MainWindow._apply_ai_preview_connection_result`, and
  `MainWindow._render_ai_engine_state`, and that connection state is separate
  from AI generation freshness.
- `engine-connection-status-regression-proof`: simulates success/failure
  provider connection results and LOCAL ready state in-process. It expects
  `manual_refresh_only_writer=false`, `connection_freshness_separated=true`,
  `connecting_timeout_supported=true`, `provider_external_call_count=0`, and
  no order-risk flags.
- `engine-connection-key-refresh-regression-proof`: simulates the key-refresh
  writer conflict: startup connecting/failed/check-needed, API connection test
  success, manual AI refresh generation-not-fresh, generation failure, stale old
  failure, latest actual connection failure, and provider-change invalidation.
  It expects generation-only events to keep provider connection status connected,
  stale old failures to be ignored, latest connection failure to downgrade to
  failed, and `provider_external_call_count=0`.
- `provider-settings-runtime-ssot-diagnostic`: verifies provider normalization
  and key/model storage separation. Saved values are `openai`, `gemini`, and
  `local`; UI/session values are `gpt`, `gemini`, and `basic`. It also verifies
  that Local/basic paths do not read OpenAI/Gemini secrets.
- `provider-settings-restart-restore-regression-proof`: simulates saved OpenAI
  settings being restored after a stale failure. It expects the selected
  provider to restore through the saved-to-session mapping and stale failure to
  clear to check-needed without a fake connected state.
- `provider-switching-cross-provider-regression-proof`: simulates OpenAI and
  Gemini status switching. It expects each provider to keep its own connection
  snapshot, with no cross-provider failure/status contamination and no provider
  external calls.
- `provider-key-resolution-bootstrap-trace`: compares safe key fingerprints for
  connection-test, startup-check, generation, and runtime provider resolver
  paths. It expects the same provider-specific stored key fingerprint for
  OpenAI/Gemini, no Local secret fallthrough, and no provider external calls.
- `provider-key-resolution-restart-regression-proof`: simulates restart-loaded
  OpenAI key resolution and verifies that startup and generation resolvers see
  the same key fingerprint after settings load. It does not write raw keys or
  call external providers.
- `provider-connection-log-forensic-summary`: scans recent
  `data/logs/aits.log*` provider events and builds a read-only forensic timeline
  for startup connection checks, key resolution, generation success, and
  connection-status writers. It reports
  `connection_failed_but_generation_success`, `connection_failure_writer`,
  `connection_recovered_writer`, and `suspected_root_cause` without provider
  calls or raw key logging.
  failed, `provider_external_call_count=0`, and no order-risk flags.
- `provider-smoke`: runs one explicit provider refresh only when
  `--allow-provider-calls` is supplied. For GPT/Gemini it reports
  `generation_response_confirmed`, `generation_response_confirmed_reason`,
  `generation_request_id`, `generation_status`, `generation_status_text`,
  `generation_attempt_count`, `generation_max_attempts`,
  `generation_retry_used`, `generation_fresh`, `generation_stale`,
  `stale_reason`, `provider_selected`, `provider_actual`, `fallback_used`,
  `http_status`, `response_id_present`, `token_usage_present`, and
  `ui_generation_status_text`. A configured key or auth-ready state is not a
  generation response proof; only a provider success log or equivalent
  generation record may confirm the response. If GPT/Gemini fails and LOCAL is
  used, the report keeps the selected provider and records the fallback reason.
  Stale previous responses must not set `generation_response_confirmed=true`.
- `save-probe`: switches to the trade-log context, verifies the footer save
  selector, calls the trade-log persistence handler directly, and records
  save proof without clicking AI refresh or making provider calls.
- `riskguard-proof`: runs synthetic dry-run order-candidate fixtures against
  `app/services/risk_guard.py`. It does not create provider calls, click AI
  refresh, submit orders, or require a Qt window.
- `riskguard-active-path-proof`: creates the real Qt window, runs one guarded
  orchestrator cycle without clicking AI refresh, and verifies that
  `RiskGuardActivePath` metadata/log proof is produced before the disabled
  order adapter boundary.
- `riskguard-active-path-candidate-proof`: injects deterministic dry-run
  candidates into the app execution path and verifies RiskGuard metadata
  reaches `ActionItem` and `ExecutionBridge`.
- `top-markets-feed-proof`: performs one read-only public Upbit market/ticker
  diagnostic for Basic candidate input. It reports raw market count, KRW market
  count, ticker count, detected volume/trade-value fields, filtered count, top
  market count, sample top markets, and a concrete `empty_reason` when the feed
  is empty. This mode allows only public market-data GET reads; provider POST,
  orders, Managed Pool mutation, sell, cancel, and retry remain forbidden.
- `basic-candidate-discovery-proof`: creates the Qt window and runs the Basic
  candidate scan observe-only. It now uses the same public market-data read
  boundary as `top-markets-feed-proof`, so `top_markets_empty` is not caused by
  the dry-read network guard. Reports must keep
  `managed_pool_mutation_performed=false`, `provider_external_call_count=0`,
  and zero place/cancel/sell/retry calls.
- `managed-pool-promotion-policy-proof`: runs fixture coverage for the
  quality-gated Basic promotion policy and, when available, applies the policy
  to the latest `basic-candidate-discovery-proof` report. It verifies max pool
  size from the supplied config as a cap, `user_added` protection, holding
  protection until liquidation, `basic_added` removal candidates, rotation
  intent creation, duplicate candidate ignoring, `actual_mutation_performed=false`,
  and zero order calls.
- `managed-pool-promotion-quality-gate-proof`: GUI-free fixture proof for the
  promotion quality gate. It verifies `fill_to_max=false`,
  `promotion_min_score`, max-as-cap behavior, low-score rejection,
  already-managed rejection, candidate pass/fail counts, rejected candidate
  reasons, and zero provider/order calls.
- `managed-pool-promotion-quality-live-proof`: observe-only live Basic
  candidate proof. It reads current Managed Pool rows, runs the Basic candidate
  scan, applies the promotion quality gate, and reports score distribution,
  quality pass/fail counts, planned additions, rejected candidates, and
  `not_filled_reason` without mutating rows.
- `managed-pool-quality-ranked-rebuild-proof`: GUI-free fixture proof for the
  `바로적용` quality rebuild contract. It preserves protected rows, re-evaluates
  existing `basic_added` rows, removes low-score or lower-ranked automatic rows,
  adds higher-quality candidates, treats the max as a cap, and performs no
  mutation or order calls.
- `managed-pool-quality-ranked-rebuild-live-proof`: observe-only public-feed
  proof for the same rebuild contract using saved Managed Pool rows and current
  public top-market candidates. It reports protected keep rows, current
  automatic rows, planned keep/add/remove, remove reasons, score distribution,
  and expected after-count without mutating rows.
- `managed-pool-auto-promotion-apply-proof`: creates the Qt window, reads the
  Managed Pool max-size UI setting, optionally overrides it with
  `--max-managed`, backs up current rows under `data/managed_pool_backups`, runs
  Basic candidate discovery, and applies `planned_add` only when
  `--apply-add-only` is present. It must report `actual_remove_count=0`,
  `actual_rotation_count=0`, `provider_external_call_count=0`, zero
  place/cancel/sell/retry calls, and `after_count <= configured_max_managed_pool_size`.
- `managed-pool-max-size-apply-button-proof`: runs a fixture proof for the
  Managed Pool footer `바로적용` trim policy. It simulates reducing the max size
  from `--from-max` to `--to-max`, verifies only unprotected `basic_added` rows
  are removed, preserves user-added, trade-hold, holding, and protected seed
  rows, and performs no real Managed Pool mutation or order calls.
- `managed-pool-max-size-apply-button-actual-proof`: creates the Qt window and
  invokes the same max-size trim helper as the `바로적용` button when
  `--apply-trim` is present. It backs up current rows, persists the trim,
  verifies readback, reports `protected_overflow` when protected rows prevent
  reaching the target, and must keep provider calls, rotation execution, and
  order calls at zero.
- `managed-pool-max-size-apply-button-sync-proof`: fixture proof for the
  `바로적용` sync contract. It verifies count-increase add-only behavior,
  count-decrease protected trim behavior, no-op behavior, source tagging, user
  protection, trade-hold protection, holding protection, seed protection,
  messages, and zero order/provider calls.
- `managed-pool-max-size-apply-button-sync-actual-proof`: creates the Qt window
  and invokes the same sync helper as the `바로적용` button when `--apply-sync`
  is present. If current count is below `--to-max`, it runs the Basic candidate
  scan and persists `basic_added` rows up to the max. If current count is above
  max, it trims only unprotected `basic_added` rows. Rotation and order calls
  must remain zero.
- `live-preflight-locked-proof`: evaluates the final live-order preflight lock
  with deterministic fixtures. It does not create paper trading, virtual
  trading, mock processors, provider calls, or order submissions.
- `live-one-shot-unlock-contract-proof`: validates the one-shot unlock
  contract, consume/reuse blocking, duplicate lock blocking, and valid unlock
  preflight input without submitting orders.
- `live-minimum-real-order-test`: high-risk one-shot KRW-BTC buy test mode.
  It refuses to run without the exact confirm phrase, checks Upbit account/key
  readiness, KRW balance, ticker freshness, RiskGuard, One-Shot Unlock, and
  LiveOrderPreflight before reaching the single allowed order-service call.
  If any pre-order condition fails, it stops without submitting an order.
  The 2026-06-29 funded retry produced report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_045413_391177.json`
  with one `KRW-BTC` buy request, HTTP `201`, submitted count `1`, immediate
  unlock consumption, relock, duplicate lock, and repeat-order block proof.
- `live-order-post-trade-reconciliation`: read-only order-status and balance
  reconciliation for the single known live order uuid. It performs Upbit GET
  order lookup and account balance lookup only. It does not place, cancel, sell,
  or retry orders. The first reconciliation report was
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_050259_116145.json`.
  The final audit recheck used
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_051206_771216.json`
  and again confirmed zero place/cancel/sell/retry calls.
  Interpret raw exchange state using
  `app/docs/aits_live_order_state_policy_v1.md`; the first live order is
  classified as `partially_filled_cancelled_remainder`, not as a simple failed
  cancellation.
  Restart persistence proof later used dry-read report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052941_859748.json`
  and reconciliation report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_052957_387433.json`;
  relock, duplicate lock, and repeat-order blocking remained true.
  The 60 minute post-order passive proof used final dry-read report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064924_106372.json`
  and final reconciliation report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_064935_630819.json`;
  no place/cancel/sell/retry, provider external generation, or order-risk marker
  appeared during the passive window.
  The read-only reconciliation hardening report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_081228_882109.json`
  adds `raw_order_state`, `normalized_order_state`,
  `normalized_order_action`, `reconciliation_reason`, structured
  `balance_reconciliation`, explicit place/cancel/sell/retry call counts, and
  `no_retry_enforced`. For the first order uuid it reports raw state `cancel`,
  normalized state `partially_filled_cancelled_remainder`, reconciliation
  status `reconciled`, zero balance delta, relock true, duplicate lock true,
  repeat block true, and zero place/cancel/sell/retry calls.
- `live-2h-guarded-window-preflight-proof`: evaluates the future 2 hour live
  guarded window contract without clicking AITS ON and without placing,
  cancelling, selling, or retrying orders. It verifies the 120 minute duration,
  10000 KRW per-order amount, 12000 KRW per-order hard cap, 20000 KRW total
  cap, max order count 2, 600 second interval, sell/cancel/retry disabled
  policy, and incident-stop behavior. It also creates and opens a smoke
  incident markdown report.
- `live-2h-guarded-window-order-path-cap-proof`: verifies that the future
  guarded-window order path uses the same 10000 KRW order unit, 12000 KRW
  per-order hard cap, 20000 KRW total cap, max order count 2, and 600 second
  interval across GuardedWindow, RiskGuard, One-Shot Unlock,
  LiveOrderPreflight, OrderAdapter metadata, and OrderService request scope.
  It does not click AITS ON and does not call `OrderService.place_order`.
- `live-2h-guarded-window`: runtime harness mode for the later guarded-window
  execution Goal. In `--dry-run-no-on` smoke mode it validates the confirm
  phrase, guarded-window config, baseline dry-read state, read-only
  reconciliation, guarded-window preflight proof, order-path cap proof, AITS ON
  selector discovery, monitoring loop wiring, incident markdown creation and
  Notepad auto-open, and final live-window report creation. It must report
  `aits_on_clicked=false`, zero order/cancel/sell/retry calls, and zero
  provider external calls. Removing `--dry-run-no-on` is allowed only in the
  later explicit live-window Goal.

## Safety Rules

- Default modes block provider HTTP POST calls.
- Public market feed proof modes may read Upbit public market/ticker endpoints
  only. They must not call provider APIs, account/order APIs, or mutate Managed
  Pool rows.
- `managed-pool-promotion-policy-proof` is policy planning only. Rotation
  `sell_candidate` / `buy_candidate` fields are review intent, not order
  execution, and must always carry `actual_order=false`.
- `managed-pool-promotion-quality-gate-proof` and
  `managed-pool-promotion-quality-live-proof` treat
  `max_managed_pool_size` as a cap, not a target. Reports must keep
  `fill_to_max=false`, include candidate pass/fail reasons, and avoid adding
  weak candidates just to fill remaining slots.
- `managed-pool-quality-ranked-rebuild-proof` and
  `managed-pool-quality-ranked-rebuild-live-proof` extend that rule to existing
  automatic rows: non-protected `basic_added` rows are re-ranked against current
  candidates, while user-added, trade-hold, holding/holding-display, and
  protected seed rows must never appear in `planned_remove`.
- `rotation-intent-ux-proof --fixture score-gap` verifies the observe-only
  `aits_rotation_intent_v1` UX payload. It must create the 60 score versus 70
  score rotation pair, include tooltip/status samples, and report
  `actual_order=false`, `rotation_execution=false`, and
  `managed_pool_mutation=false`.
- `rotation-intent-live-candidate-proof --observe-only` reads current Managed
  Pool rows and Basic candidates, then reports rotation intent pairs or an
  explicit `no_rotation_reason`. It must not mutate rows, execute rotation, or
  call provider/order paths.
- `rotation-intent-live-candidate-feed-proof --observe-only` is the read-only
  public-feed variant. It does not open the GUI; it allows Upbit public
  market/ticker GET reads, blocks provider POST and order/private paths, reads
  saved Managed Pool rows, builds proof-only candidates from the live top
  markets, and reports rotation intent pairs or a non-feed
  `no_rotation_reason`.
- `holdings-to-managed-row-proof --observe-only` injects saved settings into
  the read-only account service, calls the holdings snapshot path, compares
  live holdings with saved Managed Pool rows, and reports matched rows,
  missing holding flags, `would_mark_holding`, dust filtering,
  `holding_display_count`, `holding_eligible_count`, `would_display_holding`,
  `would_mark_holding_eligible`, tooltip samples, and
  `managed_pool_mutation=false`. Dust balances below `5000 KRW` are display
  holdings but not rotation-eligible holdings.
- `managed-pool-holding-display-sync-proof --observe-only` verifies the
  display-only Managed Pool overlay. It reads holdings, matches only existing
  Managed Pool rows, reports outside holdings without adding them, confirms row
  count is unchanged, and samples the small-holding tooltip/status payload.
- `rotation-eligibility-from-holdings-proof --observe-only` combines the
  holdings snapshot with public top-market candidates. It uses eligible
  holding rows only in memory, never persists them, and reports whether
  `no_holding_rows_for_rotation` becomes a score/condition reason or a
  dust/min-value reason.
- `managed-pool-auto-promotion-apply-proof --apply-add-only` is the only
  harness mode that may persist Managed Pool additions in this policy family.
  It must not remove existing rows, execute rotation, or exceed the configured
  max. If cap or preservation checks fail, it rolls back to the backup rows.
- The harness skips startup provider verification inside the harness process.
- `AI 분석 새로고침` is located but never clicked in dry modes.
- Order-related UI or service calls are not part of the harness.
- Any report containing `AITS ON`, `Live`, `submitted=1`,
  `order_allowed=True`, `real_order=True`, or order bridge keywords is NO-GO.
  The only exception is the explicit `live-minimum-real-order-test` report,
  where `real_order=True` and `submitted_count=1` may appear only for the one
  sanctioned KRW-BTC buy response.
- `live-2h-guarded-window-preflight-proof` must always report
  `aits_on_clicked=false`, `place_order_call_count=0`, `cancel_call_count=0`,
  `sell_call_count=0`, and `retry_call_count=0`.
- `live-2h-guarded-window-order-path-cap-proof` must always report
  `allowed_10000_policy_passed=true`, `aits_on_clicked=false`,
  `place_order_call_count=0`, `cancel_call_count=0`, `sell_call_count=0`, and
  `retry_call_count=0`. The 5000 KRW amount remains historical evidence for
  the first one-shot order only; it is not the guarded-window order unit.
  The first cap-alignment report was
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_091912_905642.json`
  and passed all eight fixtures without an order call.
- `live-2h-guarded-window --dry-run-no-on` must always report
  `confirm_phrase_valid=true`, `aits_on_selector_found=true`,
  `aits_on_clicked=false`, `place_order_call_count=0`, `cancel_call_count=0`,
  `sell_call_count=0`, `retry_call_count=0`,
  `provider_external_call_count=0`, and a smoke incident markdown path. It
  writes the normal runtime smoke JSON plus
  `data/live_window_reports/aits_live_2h_guarded_window_report_smoke_*.json`
  and a matching markdown summary.

## Stable Selectors

The harness prefers Qt `objectName` and falls back to `smokeObjectName`
properties where existing object names are already used by stylesheets.

Core selectors include:

- `main_window_aits`
- `lbl_aits_power_state`
- `lbl_aits_safety_state`
- `lbl_selected_ai_engine`
- `lbl_applied_ai_engine`
- `lbl_provider_connection_state`
- `cmb_ai_provider`
- `tab_aits_managed`
- `tab_trade_log`
- `tab_investment`
- `tab_ai_policy_center`
- `tab_common_settings`
- `tbl_ai_managed`
- `btn_ai_analysis_refresh`
- `btn_ai_status_refresh`
- `tbl_trade_log`
- `pnl_trade_log_detail`
- `btn_trade_log_save`
- `btn_manual_sell_all`
- AITS run selector discovery prefers the `btn_run_toggle` attribute and the
  `StopButton` objectName. Discovery is read-only unless a later live-window
  Goal explicitly removes `--dry-run-no-on`.

## Provider Calls

The harness does not add automatic GPT, Gemini, OpenAI, Gemini, Ollama, or
other external AI calls. Provider runtime smoke must be run only by a later Goal
that explicitly permits the exact provider and call count.

## Provider-Smoke CLI

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-smoke --allow-provider-calls --provider local --max-provider-calls 1
```

Arguments:

- `--provider local|gpt|gemini`: required for provider-smoke.
- `--max-provider-calls N`: defaults to `1`; values greater than three are
  blocked. LOCAL still requires one call or fewer. GPT/Gemini may use `2` for
  retry-lifecycle proof when the Goal explicitly allows it.
- `--target-symbol KRW-...`: optional managed-row target.
- `--timeout-sec N`: maximum wait for snapshot and Journal proof.
- `--wait-after-click-sec N`: initial event-pump delay after the single click.
- `--no-click`: select provider and target only; do not click AI refresh.

Safety behavior:

- Provider-smoke refuses to run without `--allow-provider-calls` and `--provider`.
- Provider-smoke performs at most one AI refresh click.
- LOCAL provider-smoke expects zero external OpenAI/Gemini request markers.
- GPT and Gemini provider-smoke must be run only by a Goal that explicitly allows
  the exact provider and call count.
- GPT/Gemini provider-smoke maps `--max-provider-calls` to the generation retry
  budget. `1` means no retry; `2` permits one provider-generation retry. This is
  not an order retry and must not call order services.
- Reports include provider branch delta, external cost-provider request delta,
  selected symbol, latest decision group id, snapshot/Journal proof flags,
  latest trade-log row, detail excerpt, duplicate detection, and order-risk flags.
- GPT/Gemini provider-smoke uses a compact generation payload only for this
  explicit smoke mode. The normal runtime provider path is unchanged. For GPT,
  the compact smoke request records `compact_smoke=true`, `messages_count`,
  `message_chars`, `output_token_cap`, and `timeout_sec` in
  `[AITS][OpenAIProviderProof] event=request_attempt`. The timeout owner is the
  HTTP provider request; the Qt worker watchdog remains later than that request
  timeout. A successful GPT smoke requires HTTP success, response id presence,
  token usage presence, `provider_actual=gpt`, `fallback_used=false`, and
  `generation_response_confirmed=true`.
- GPT timeout handling must distinguish request timeout from stale generation
  state. Timeout failures should keep the selected provider, record fallback
  reason clearly, and show timeout status instead of reverting to a generic
  unconfirmed response label. The 2026-06-29 timeout root fix verified GPT
  provider-smoke with report
  `C:\AITS\data\runtime_smoke_reports\runtime_smoke_report_20260629_134523_490619.json`:
  `http_status=200`, response id present, token usage present,
  `provider_selected=gpt`, `provider_actual=gpt`, `fallback_used=false`,
  `generation_response_confirmed=true`, and UI status `생성 응답 확인됨`.

`--no-click` may be used without `--allow-provider-calls` to validate the
provider-smoke report schema while network guards remain installed:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-smoke --provider local --no-click
```

## Report JSON Validation

PowerShell:

```powershell
Get-Content -Raw -Encoding UTF8 data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json | ConvertFrom-Json
```

Python:

```powershell
python -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8')); print('OK')" data/runtime_smoke_reports/runtime_smoke_report_YYYYMMDD_HHMMSS.json
```

Report validation must not require provider calls. Use `dry-read`,
`dry-navigation`, or provider-smoke `--no-click` for schema checks.

## RiskGuard-Proof

Use this mode before any dry-run or small-money execution work:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
```

The mode validates seven synthetic candidates:

- `allowed_small_buy`
- `blocked_max_order`
- `blocked_position_limit`
- `blocked_daily_loss`
- `blocked_emergency_stop`
- `blocked_invalid_symbol`
- `blocked_stale_price`

The report includes:

- `riskguard_fixture_count`
- `riskguard_pass_count`
- `riskguard_fail_count`
- `riskguard_results`
- `provider_call_markers`
- `external_cost_call_delta`
- `submitted_detected`
- `order_risk_detected`
- `real_order_detected`

RiskGuard uses `risk_allowed=True` for a dry-run policy pass. It keeps
`submitted=0`, `order_allowed=False`, and `real_order=False` for both allowed
and blocked fixtures. A passing RiskGuard fixture is not live-order permission.

## RiskGuard Active Path Proof

Use this mode after RiskGuard integration changes:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-proof
```

The mode keeps network/provider guards installed, builds the real UI, then runs
one orchestrator dry-run cycle. It expects one of two safe outcomes:

- `pass`: a runtime candidate was evaluated and RiskGuard metadata was attached.
- `partial`: no execution candidate existed, but a `no_candidate` active-path
  proof was emitted.

The report includes:

- `riskguard_active_path_checked`
- `riskguard_active_path_events`
- `latest_riskguard_event`
- `riskguard_candidate_seen`
- `risk_allowed`
- `risk_blocked_reason`
- `riskguard_active_path_log_markers`

The mode must keep provider call markers at zero and must keep `submitted=0`,
`order_allowed=False`, and `real_order=False`.

## RiskGuard Active Path Candidate Fixture Proof

Use this mode when the active path is wired but the live app state does not
produce an execution candidate:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
```

The mode injects deterministic dry-run `ActionItem` fixtures into the app
execution path, calls the same RiskGuard integration helper used by the
orchestrator, and verifies `ExecutionBridge` metadata passthrough. It does not
click AI refresh, call providers, call OrderAdapter, or submit orders.

Required fixtures:

- `allowed_small_buy_path`
- `blocked_max_order_path`

The report includes:

- `riskguard_active_path_candidate_fixture_count`
- `riskguard_active_path_candidate_pass_count`
- `riskguard_active_path_candidate_results`
- `actionitem_metadata_seen`
- `execution_bridge_metadata_seen`
- `order_adapter_called`
- `order_adapter_execution_mode`

PASS requires `risk_allowed` to match each fixture, `ActionItem` and
`ExecutionBridge` metadata to be present, provider call markers to remain zero,
and `submitted=0`, `order_allowed=False`, and `real_order=False`.

## Live Preflight Locked Proof

Use this mode before any live-order unlock work:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
```

This mode keeps the AITS principle of one real-order path. It does not add paper
mode, virtual trading, or mock trading processors. It evaluates the real-order
preflight lock with deterministic fixtures and keeps every result locked. It
does not click AI refresh, does not call GPT/Gemini, does not call OrderAdapter
live execution, and does not call OrderService.

The report includes:

- `live_preflight_fixture_count`
- `live_preflight_pass_count`
- `live_preflight_fail_count`
- `live_preflight_results`
- `order_service_place_order_called`
- `order_adapter_live_branch_entered`
- `order_adapter_execution_mode`
- `submitted_detected`
- `order_risk_detected`
- `paper_mode_created`
- `virtual_trading_created`
- `mock_trading_processor_created`

PASS requires every preflight fixture to keep `locked=true`, `allowed=false`,
`submitted=0`, `order_allowed=false`, and `real_order=false`. Provider and
external-cost call markers must remain zero.

## Live One-Shot Unlock Contract Proof

Use this mode before any minimum real-order test:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
```

This mode validates the one-shot unlock contract only. It does not create paper
mode, virtual trading, simulation processors, or mock trading processors. It
does not call providers, does not enter the OrderAdapter live branch, and does
not call OrderService.

Fixtures:

- `no_unlock`
- `invalid_confirm_token`
- `amount_exceeds_unlock_cap`
- `expired_unlock`
- `valid_unlock_preflight_pass_but_no_order_submit`
- `consumed_unlock_reuse`
- `duplicate_lock_reuse`

The valid fixture may report `allowed_for_preflight=true`; that is not order
permission. PASS still requires `submitted=0`, `order_allowed=false`,
`real_order=false`, and `order_service_place_order_called=false`.

Report fields include:

- `one_shot_unlock_fixture_count`
- `one_shot_unlock_pass_count`
- `one_shot_unlock_fail_count`
- `one_shot_unlock_results`
- `valid_unlock_seen`
- `consumed_reuse_blocked`
- `duplicate_reuse_blocked`
- `order_service_place_order_called`
- `order_adapter_live_branch_entered`

## Minimum Real Order Preflight Review

Before any future minimum real-order attempt, run and record:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-read
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode dry-navigation
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode riskguard-active-path-candidate-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-locked-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-one-shot-unlock-contract-proof
```

The review plan lives at
`app/docs/aits_live_minimum_real_order_test_plan_v1.md`. It does not run an
order; it defines the single allowed future candidate, the hard cap, the
one-shot confirmation phrase, duplicate lock, failure handling, and immediate
relock policy.

Any provider call marker, order-risk marker, `submitted=1`,
`order_allowed=true`, or `real_order=true` before the future real-order Goal is
NO-GO.

## Save-Probe

Use this mode before persistence/restart smoke:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode save-probe
```

The probe verifies `btn_trade_log_save`, navigates to the trade-log context, and
then calls the same trade-log save handler used by the footer save dispatcher.
It intentionally avoids the modal success message that can block automation when
the button is clicked directly.

Save-probe report fields include:

- `save_button_found`
- `save_handler_entered`
- `save_completed`
- `save_elapsed_ms`
- `save_log_start_delta`
- `save_log_finish_delta`
- `trade_log_row_count_before`
- `trade_log_row_count_after`
- `latest_row_before`
- `latest_row_after`
- `journal_before`
- `journal_after`
- `provider_call_delta`
- `external_cost_call_delta`

PASS requires the save handler to return within 10 seconds, a finish log to be
observed, no provider-call delta, unchanged latest trade-log row semantics, and
no order-risk markers. A direct button-click path may show a success
`QMessageBox`; that is a UI feedback path, not a persistence requirement.

## Manual Order UI Safety

The harness reports manual high-risk order controls without clicking them.
`manual_order_buttons` includes found/visible/enabled state for selectors such
as `btn_manual_sell_all`. Any visible and enabled manual order button is treated
as an order-risk condition in dry-read and dry-navigation reports.

Manual sell, panic sell, liquidation, and emergency order controls must remain
disabled in Shadow/AITS OFF mode. Unlocking manual order UI requires a separate
high-risk Goal with RiskGuard, ExecutionBridge, OrderAdapter, and user
confirmation proof. The smoke harness must not click these controls.

## Engine Readiness Fields

Dry-read and provider-smoke reports include the AITS ON engine-readiness
contract used by the UI gate:

- `engine_ready_for_run`
- `engine_ready_reason`
- `engine_not_ready_reason`
- `generation_response_confirmed`
- `generation_fresh`
- `generation_stale`
- `response_id_present`
- `token_usage_present`
- `provider_selected`
- `provider_actual`
- `fallback_used`
- `active_engine`
- `on_gate_expected_engine`
- `connection_state_simple`
- `connection_detail_text`

For GPT/Gemini, readiness requires a fresh confirmed generation response for
the selected provider with response-id or token-usage proof and no LOCAL
fallback. Auth-only, timeout, fallback, and stale preview states must remain
not-ready. Engine readiness is not order permission. `connection_state_text`
uses the simplified user-facing state (`연결중`, `연결됨`, `연결오류`), while
`connection_detail_text` may retain diagnostic context.

## Trading Boundary

The harness does not modify Router, Execution, Order, RiskGuard, repository, or
trade DB behavior. Runtime safety remains observe-only with `submitted=0`,
`order_allowed=False`, and `real_order=False`.

## Provider Startup Readiness Proof

`provider-startup-readiness-proof` verifies the startup/provider-apply readiness
path without clicking AITS ON and without orders:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode provider-startup-readiness-proof --provider gpt --allow-provider-calls --max-provider-calls 1 --target-symbol KRW-BTC --timeout-sec 90
```

The mode enables `AITS_STARTUP_READINESS_PREFLIGHT=1` for the harness session,
keeps ordinary dry-read provider calls blocked, waits for the `startup_generation`
preflight, and reports:

- `startup_readiness_preflight_attempted`
- `generation_source`
- `generation_request_id`
- `generation_status`
- `connection_state_simple`
- `engine_ready_for_run`
- `active_engine`
- `provider_actual`
- `fallback_used`
- `external_cost_call_count`
- `provider_call_count_with_worker_markers`

PASS requires `connection_state_simple=연결됨`, fresh confirmed generation proof,
matching active provider, no fallback, provider external calls within budget, and
no order-risk markers.

## Real App Startup Readiness Proof

`real-app-startup-readiness-proof` verifies the actual app startup path instead
of directly invoking the startup helper on an already constructed harness
window:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode real-app-startup-readiness-proof --provider gpt --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

The mode launches `run.py` as a separate app process, removes
`AITS_QT_SMOKE_HARNESS` from that child environment, observes
`data/logs/aits.log`, and never clicks AITS ON or order controls. It reports:

- `startup_readiness_scheduled`
- `startup_readiness_skip_reason`
- `startup_worker_started`
- `startup_worker_result_seen`
- `startup_ui_applied`
- `connection_state_simple_after`
- `generation_source`
- `generation_status`
- `generation_request_id`
- `engine_ready_for_run`
- `provider_call_count`
- `provider_call_count_with_worker_markers`
- `external_cost_call_count`
- `provider_actual`
- `fallback_used`

PASS requires scheduled startup readiness, worker start/result, UI application
to the connected state, one or fewer external provider calls, no fallback, and
no order-risk markers. This mode exists because a helper-invocation proof can
pass while the real `run.py` startup path still fails to schedule or apply the
preflight.

## Basic Candidate Discovery Proof

`basic-candidate-discovery-proof` is an observe-only proof for the Basic Engine
candidate discovery path:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode basic-candidate-discovery-proof --observe-only --max-candidates 10
```

The mode does not click AITS ON, does not call providers, does not place orders,
and does not mutate the Managed Pool. It observes the active scanner owner
(`MainWindow._load_market_explorer_initial_data`), the Basic score helper
(`MainWindow._calc_basic_ai_score`), current `managed_pool_rows`, and the current
soft rotation payload. The report includes:

- `basic_candidate_scan_called`
- `basic_candidate_scan_success`
- `market_data_ready`
- `market_count`
- `top_markets_count`
- `candidate_count`
- `top_candidates`
- `no_candidate_reason`
- `managed_pool_symbols_before`
- `managed_pool_symbols_after`
- `would_add`
- `would_keep`
- `would_remove`
- `would_rotate`
- `managed_pool_mutation_performed`

`would_add`, `would_remove`, and `would_rotate` are only proof fields. A PASS
requires the scan owner to run, Managed Pool mutation to remain false, provider
external calls to remain zero, and order-risk counters to remain zero. If
candidate count is zero, `no_candidate_reason` is the primary result.

## Managed Pool Sync Explain Proof

`managed-pool-max-size-apply-button-sync-proof` and
`managed-pool-max-size-apply-button-sync-actual-proof` include explainable UX
fields for the max-size `바로적용` action:

- `explain_payload`
- `explain_schema`
- `explain_message`
- `explain_added`
- `explain_removed`
- `explain_protected`
- `explain_skipped`
- `ui_summary_text`
- `journal_written`
- `journal_text`

The fixture proof covers add, trim, no-op, no-candidate, and protected-overflow
message paths. PASS requires the explain payload to remain JSON-safe and order
risk to remain false.

## Managed Pool AI Review Proof

`managed-pool-ai-review-queue-proof` observes the Managed Pool review queue
without calling GPT/Gemini and without changing rows:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-review-queue-proof --observe-only
```

The report records the active owner
`MainWindow._build_managed_pool_ai_review_queue`, current queue symbols,
fresh/stale/analysis-required state, and the manual reanalysis reason. Provider
external calls must remain `0`.

`managed-pool-ai-opinion-flow-proof` builds LOCAL/calculation-based
`managed_pool_ai_opinion_v1` payloads:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-flow-proof --observe-only --provider local
```

The payload is an opinion/report surface only. It must keep
`order_execution=false`, `final_action_unchanged=true`, Managed Pool mutation
false, and provider external call count `0`. GPT/Gemini one-shot opinion proof
requires a separate Goal.

`managed-pool-gpt-one-shot-opinion-proof` is the explicit provider-call proof
for exactly one Managed Pool symbol:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

The mode builds a compact Managed Pool opinion context, enables the existing
one-shot provider gate, and normalizes the response into
`managed_pool_ai_opinion_v1`. It must not mutate Managed Pool rows, must not
change DecisionRouter final action, and must keep provider call count `<= 1`.

`managed-pool-ai-opinion-ui-apply-proof` applies a LOCAL opinion payload to the
same display-only overlay path used by the table renderer:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-ui-apply-proof --observe-only --provider local --target-symbol KRW-BTC
```

`managed-pool-gpt-one-shot-opinion-ui-proof` first runs the one-shot provider
opinion proof and then verifies the same overlay status/tooltip samples:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-ui-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

Both modes must report `overlay_created=true`, a status sample, a tooltip
sample, `managed_pool_mutation=false`, `order_execution=false`, and
`final_action_unchanged=true`. LOCAL overlay proof must keep provider calls at
`0`; GPT/Gemini one-shot UI proof must keep provider calls `<= 1`.

### managed-pool-manual-ai-refresh-row-freshness-proof

`managed-pool-manual-ai-refresh-row-freshness-proof` injects a LOCAL/mock manual AI refresh result into the same display-only Managed Pool overlay path used by the UI. The report records `analysis_required_before`, `overlay_created`, `overlay_source`, `analysis_required_after`, `reason_after`, `tooltip_sample`, `status_sample`, `row_persistence_mutation=false`, `provider_external_call_count=0`, and order/final-action safety fields.

AI opinion tooltip samples also report Korean label polish checks:
`tooltip_korean_labels_applied`, `tooltip_system_labels_removed`, and
`tooltip_freshness_humanized`. These fields verify display copy only; the
underlying `managed_pool_ai_opinion_v1` payload and freshness decision logic are
unchanged.

`managed-pool-gpt-one-shot-opinion-proof` now records the dedicated
`managed_pool_ai_opinion_request_v1` request schema, compact payload fields,
normalized opinion payload, response id/token usage presence, and
`reason_quality_flags`. PASS requires provider call count `<= 1`, a confirmed
response, user-facing rationale that is not only an execution-block reason,
`order_execution=false`, `final_action_unchanged=true`, and Managed Pool mutation
false.

### managed-pool-manual-refresh-dedicated-opinion-proof

`managed-pool-manual-refresh-dedicated-opinion-proof` verifies that the manual Managed Pool AI refresh path uses `managed_pool_ai_opinion_request_v1` and normalizes the provider result into `managed_pool_ai_opinion_v1` before applying the display-only row overlay.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-manual-refresh-dedicated-opinion-proof --provider local --target-symbol KRW-ETH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-manual-refresh-dedicated-opinion-proof --provider gpt --target-symbol KRW-ETH --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

PASS requires `dedicated_payload_used=true`, `payload_schema=managed_pool_ai_opinion_request_v1`, a normalized opinion payload, overlay application, `order_execution=false`, `final_action_unchanged=true`, `actual_order=false`, `managed_pool_mutation=false`, and `order_risk_detected=false`. LOCAL proof keeps provider calls at `0`; GPT/Gemini proof requires the explicit provider-call flag and a call budget of `<= 1`.

The GPT actual-call variant also verifies the fresh reason consistency guard.
For a successful manual refresh overlay, the report records
`freshness=fresh_manual_refresh`, `reason_consistent_with_freshness=true`,
`stale_reason_leaked=false`, `stale_next_action_leaked=false`,
`stale_reason_replaced`, and `fresh_tooltip_stale_phrase_found=false`.
The fresh overlay tooltip sample is scanned for stale/manual-required phrases
such as manual-required, analysis-required, and new-analysis-recommended copy.
The proof remains display-only and must keep `order_execution=false`,
`final_action_unchanged=true`, `actual_order=false`, and
`managed_pool_mutation=false`.

The GPT/Gemini actual-call variant also reports safe response metadata:
`response_id_present`, `token_usage_present`, `response_id`, `token_usage`,
`response_metadata_extracted`, and `response_metadata_missing_reason`. PASS for
the metadata follow-up requires `response_metadata_extracted=true`,
`response_id_present=true`, `token_usage_present=true`, and
`tooltip_exposes_token_usage=false`. LOCAL observe-only proof may leave response
metadata absent and should report a clear non-external-provider reason.

### managed-pool-manual-refresh-metadata-audit-proof

`managed-pool-manual-refresh-metadata-audit-proof` verifies the read-only audit
path for manual Managed Pool GPT/Gemini refresh metadata. It reuses the
dedicated manual refresh opinion flow, then emits a
`managed_pool_ai_opinion_audit_v1` payload for validation and cost tracking.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-manual-refresh-metadata-audit-proof --provider local --target-symbol KRW-ETH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-manual-refresh-metadata-audit-proof --provider gpt --target-symbol KRW-ETH --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

The audit payload includes `target_symbol`, `provider`, `request_id`,
`response_id`, `response_confirmed`, token counts, provider call count, request
schema, opinion schema, and safety flags. It must not include raw prompts, raw
provider responses, API keys, or secret bodies. PASS for GPT/Gemini requires
`response_id_present=true`, `token_usage_present=true`,
`provider_external_call_count<=1`, `tooltip_exposes_token_usage=false`,
`raw_payload_logged=false`, `raw_response_logged=false`, `secret_logged=false`,
`order_execution=false`, `final_action_unchanged=true`, `actual_order=false`,
and `managed_pool_mutation=false`. LOCAL observe-only proof emits the same audit
schema with safe null response metadata and provider calls fixed at `0`.

### buy-ready-order-intent-contract-proof

`buy-ready-order-intent-contract-proof` verifies the observe-only contract
between Basic `Buy Ready` display state and a possible order-intent candidate.
It reads the latest Basic candidate report and Managed Pool rows, reports
`buy_ready_symbols`, evaluates `aits_order_intent_candidate_contract_v1`, and
keeps actual emission disabled.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode buy-ready-order-intent-contract-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode buy-ready-order-intent-contract-proof --observe-only
```

PASS requires the candidate symbols and block reasons to be explicit while
keeping `actual_order_intent_emitted=false`, `decision_router_called=false`,
`risk_guard_called=false`, `live_preflight_called=false`,
`order_service_called=false`, `submitted_count=0`,
`provider_external_call_count=0`, and `order_risk_detected=false`.

`buy-ready-ai-opinion-freshness-unblock-proof` verifies the same contract after
injecting an in-memory LOCAL/mock `managed_pool_ai_opinion_v1` context for a
Buy Ready row. It checks that missing opinion/freshness reasons are removed and
that `would_promote_to_order_intent=true` can be reported without actual
emission.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode buy-ready-ai-opinion-freshness-unblock-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode buy-ready-ai-opinion-freshness-unblock-proof --target-symbol KRW-PYTH --observe-only
```

`order-intent-candidate-inert-bridge-proof` builds the inert
`aits_order_intent_candidate_v1` report object from a
`would_promote_to_order_intent=true` contract result. It never emits the
candidate to Router/Risk/Preflight/Order paths.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-candidate-inert-bridge-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-candidate-inert-bridge-live-proof --target-symbol KRW-PYTH --observe-only
```

PASS requires `candidate_created=true`, `candidate_valid=true`,
`actual_order_intent_emitted=false`, `decision_router_called=false`,
`risk_guard_called=false`, `live_preflight_called=false`,
`order_service_called=false`, `order_adapter_called=false`,
`submitted_count=0`, `provider_external_call_count=0`, and
`order_risk_detected=false`.

`order-intent-router-handoff-readiness-proof` evaluates the inert candidate
against `aits_order_intent_router_handoff_readiness_v1`. It reports
`router_handoff_ready`, `blockers`, `warnings`, and per-check details, but it
does not call DecisionRouter, RiskGuard, LivePreflight, OrderService, or
OrderAdapter.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-router-handoff-readiness-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-router-handoff-readiness-live-proof --target-symbol KRW-PYTH --observe-only
```

PASS requires `router_handoff_ready=true` for the valid/live candidate and
blocked readiness for invalid fixtures while keeping
`actual_order_intent_emitted=false`, `decision_router_called=false`,
`risk_guard_called=false`, `live_preflight_called=false`,
`order_service_called=false`, `order_adapter_called=false`,
`submitted_count=0`, `provider_external_call_count=0`, and
`order_risk_detected=false`.

`order-intent-router-validation-stub-proof` builds
`aits_order_intent_router_validation_stub_v1` from the inert candidate and
handoff readiness report. It validates the payload shape only; it does not call
DecisionRouter, RiskGuard, LivePreflight, OrderService, or OrderAdapter.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-router-validation-stub-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-router-validation-stub-live-proof --target-symbol KRW-PYTH --observe-only
```

PASS requires `router_validation_payload_ready=true` for the valid/live
candidate, invalid fixtures to return validation errors, `user_added` to remain
`user_added_requires_live_policy_confirmation` as a policy warning, and all
order/Router/Risk/Preflight/Order call flags to remain false.

`order-intent-source-live-policy-stub-proof` applies
`aits_order_intent_source_live_policy_v1` to the Router validation stub payload.
It proves source policy readiness only; it does not emit an order intent or call
DecisionRouter, RiskGuard, LivePreflight, OrderService, or OrderAdapter.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-source-live-policy-stub-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-source-live-policy-stub-live-proof --target-symbol KRW-PYTH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-source-live-policy-stub-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --observe-only
```

Without approval, PASS requires `source_policy_ready=false`,
`policy_blockers` containing `user_added_not_session_approved`, and
`router_validation_payload_ready=false`. With exact approval, PASS requires
`source_policy_ready=true`, `policy_blockers=[]`, no
`user_added_requires_live_policy_confirmation` warning, and
`router_validation_payload_ready=true`. Both paths must keep all emit and
Router/Risk/Preflight/Order call flags false.

`order-intent-one-shot-unlock-readiness-proof` applies
`aits_order_intent_one_shot_unlock_readiness_v1` after source policy readiness.
It proves only the readiness contract. It does not execute or consume a
one-shot unlock and does not emit an order intent.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-one-shot-unlock-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --observe-only
```

Without mock unlock approval, PASS requires `one_shot_unlock_ready=false`,
`policy_blockers` containing `one_shot_unlock_required`, and
`live_order_readiness=false`. With exact mock approval, PASS requires
`one_shot_unlock_ready=true`, `policy_blockers=[]`, and
`live_order_readiness=true`. Both paths must keep `unlock_service_called=false`,
`actual_order_intent_emitted=false`, all Router/Risk/Preflight/Order call flags
false, `submitted_count=0`, `provider_external_call_count=0`, and
`order_risk_detected=false`.

`order-intent-live-preflight-readiness-proof` applies
`aits_order_intent_live_preflight_readiness_v1` after one-shot unlock readiness.
It verifies preflight-before-preflight conditions only; it does not call the
real LivePreflight service.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-fixture-proof
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode order-intent-live-preflight-readiness-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --observe-only
```

PASS requires the valid mock-unlock path to report
`live_preflight_readiness=true` while keeping `live_preflight_called=false`,
`actual_order_intent_emitted=false`, Router/Risk/Order call flags false,
`submitted_count=0`, and `provider_external_call_count=0`. Without mock unlock,
the live proof remains blocked before LivePreflight readiness.

The future actual read-only adapter design is documented in
`app/docs/aits_live_preflight_readonly_adapter_contract_v1.md`. It is not a
runtime smoke mode yet. The contract requires `would_call_live_preflight=false`,
`live_preflight_called=false`, `unlock_consumed=false`,
`actual_order_intent_emitted=false`, `actual_order=false`, and `submitted=0`.
The next implementation Goal is limited to a skeleton/proof adapter and must not
call the real LivePreflight service.

`live-preflight-readonly-adapter-skeleton-fixture-proof` validates
`aits_live_preflight_readonly_adapter_contract_v1` with fixture chains. The
valid chain reports `adapter_ready=true`; invalid chains report
`adapter_ready=false` with blockers such as
`live_preflight_readiness_not_ready`, `one_shot_unlock_not_ready`,
`submitted_nonzero`, or `order_service_reachable_true`.

`live-preflight-readonly-adapter-skeleton-live-proof` embeds the live
LivePreflight readiness proof and then builds the read-only adapter contract
payload. PASS requires `adapter_ready=true` for the mock-approved valid chain
while keeping `would_call_live_preflight=false`, `live_preflight_called=false`,
`unlock_consumed=false`, `actual_order_intent_emitted=false`,
`order_service_reachable=false`, `order_adapter_reachable=false`,
`submitted_count=0`, and `provider_external_call_count=0`.

The RiskGuard read-only adapter skeleton is documented in
`app/docs/aits_riskguard_readonly_adapter_contract_v1.md` and is covered by:

- `riskguard-readonly-adapter-skeleton-fixture-proof`
- `riskguard-readonly-adapter-skeleton-live-proof`

Both modes build only `aits_riskguard_readonly_adapter_contract_v1` objects in
the harness. They do not import or call the real RiskGuard service. PASS
requires `would_call_riskguard=false`, `risk_guard_called=false`,
`risk_decision=not_evaluated`, `would_call_live_preflight=false`,
`live_preflight_called=false`, `unlock_consumed=false`,
`actual_order_intent_emitted=false`, `actual_order=false`, `submitted=0`, and
`provider_external_call_count=0`.

The actual-readonly RiskGuard adapter proof is documented in
`app/docs/aits_riskguard_readonly_actual_adapter_design_v1.md` and is covered
by:

- `riskguard-readonly-actual-adapter-fixture-proof`
- `riskguard-readonly-actual-adapter-live-proof`

Both modes build `aits_riskguard_readonly_actual_adapter_contract_v1` objects in
the harness. They identify the RiskGuard callable contract from static strings
only and do not import or call the real RiskGuard service. PASS requires
`actual_readonly_adapter_ready=true` for the mock-approved valid chain while
keeping `would_call_riskguard=false`, `risk_guard_called=false`,
`risk_decision=not_evaluated`, `risk_result_present=false`,
`risk_guard_reachable=false`, `live_preflight_called=false`,
`unlock_consumed=false`, `actual_order=false`,
`actual_order_intent_emitted=false`, `submitted_count=0`, and
`provider_external_call_count=0`.

The LivePreflight actual-readonly adapter design review is documented in
`app/docs/aits_live_preflight_readonly_actual_adapter_design_v1.md`. It is not a
runtime smoke mode and does not change the harness. The next proof Goal may add
a harness mode, but the default contract remains
`would_call_live_preflight=false`, `live_preflight_called=false`,
`live_preflight_decision=not_evaluated`,
`live_preflight_result_present=false`, `actual_order=false`,
`actual_order_intent_emitted=false`, `submitted_count=0`, and
`provider_external_call_count=0`.

The LivePreflight actual-readonly adapter proof is covered by:

- `live-preflight-readonly-actual-adapter-fixture-proof`
- `live-preflight-readonly-actual-adapter-live-proof`

Example:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-readonly-actual-adapter-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-preflight-readonly-actual-adapter-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --observe-only
```

Both modes build `aits_live_preflight_readonly_actual_adapter_contract_v1`
objects in the harness. They identify the LivePreflight callable contract from
static strings only and do not import or call the real LivePreflight service.
PASS requires `live_preflight_actual_readonly_adapter_ready=true` for the
mock-approved valid chain while keeping `would_call_live_preflight=false`,
`live_preflight_called=false`, `live_preflight_decision=not_evaluated`,
`live_preflight_result_present=false`, `live_preflight_reachable=false`,
`would_call_riskguard=false`, `risk_guard_called=false`,
`order_service_called=false`, `order_adapter_called=false`,
`execution_bridge_reachable=false`, `unlock_consumed=false`,
`actual_order=false`, `actual_order_intent_emitted=false`,
`submitted_count=0`, and `provider_external_call_count=0`.

The live-order final gate integration proof is covered by:

- `live-order-final-gate-integration-fixture-proof`
- `live-order-final-gate-integration-live-proof`

Example:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-order-final-gate-integration-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-order-final-gate-integration-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --observe-only
```

Both modes build `aits_live_order_final_gate_integration_contract_v1` objects in
the harness. PASS requires `live_order_final_gate_ready=true` for the
mock-approved valid chain while keeping `would_emit_order_intent=false`,
`order_intent_emitted=false`, `would_consume_unlock=false`,
`unlock_consumed=false`, `actual_order=false`,
`actual_order_intent_emitted=false`, `order_service_called=false`,
`order_adapter_called=false`, `execution_bridge_called=false`,
`submitted_count=0`, and `provider_external_call_count=0`.

The live minimal order armed-but-not-submitted proof is covered by:

- `live-minimal-order-armed-fixture-proof`
- `live-minimal-order-armed-live-proof`

Example:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-armed-live-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --configured-order-amount-krw 10000 --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --operator-confirm-phrase "AITS LIVE ORDER KRW-PYTH BUY 10000" --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-armed-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --configured-order-amount-krw 11000 --intended-amount-krw 11000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --operator-confirm-phrase "AITS LIVE ORDER KRW-PYTH BUY 11000" --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-armed-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --configured-order-amount-krw 11000 --intended-amount-krw 10000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --operator-confirm-phrase "AITS LIVE ORDER KRW-PYTH BUY 10000" --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-armed-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --configured-order-amount-krw 13000 --intended-amount-krw 13000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --operator-confirm-phrase "AITS LIVE ORDER KRW-PYTH BUY 13000" --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-armed-fixture-proof --target-symbol KRW-PYTH --session-approved-symbols KRW-PYTH --mock-unlock-approved-symbols KRW-PYTH --configured-order-amount-krw 5000 --intended-amount-krw 5000 --mock-total-window-used-krw 0 --mock-submitted-count 0 --operator-confirm-phrase "AITS LIVE ORDER KRW-PYTH BUY 5000" --observe-only
```

Both modes build `aits_live_minimal_order_armed_contract_v1` objects with
`armed_mode=not_submitted`. PASS may set `live_minimal_order_armed=true`, but it
must keep `actual_order=false`, `actual_order_intent_emitted=false`,
`would_emit_order_intent=false`, `would_consume_unlock=false`,
`unlock_consumed=false`, `order_service_called=false`,
`order_adapter_called=false`, `execution_bridge_called=false`,
`submitted_count=0`, and `provider_external_call_count=0`.

The expected operator confirm phrase is based on `configured_order_amount_krw`:

`AITS LIVE ORDER {symbol} {side.upper()} {configured_order_amount_krw}`

The next allowed Goal is
`AITS-LIVE-MINIMAL-ORDER-SETTING-AMOUNT-ONE-SHOT-TEST-01`.

The setting read-path preflight is covered by:

- `live-minimal-order-setting-readpath-preflight`

Example:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-minimal-order-setting-readpath-preflight --target-symbol KRW-PYTH --observe-only
```

This mode reports the read-only mapping from UI/runtime/prefs/schema to
`configured_order_amount_krw`. The expected SSOT is
`settings.strategy.order_amount_krw`; 10,000 KRW is the current/default example,
not a hardcoded live-order amount.

### managed-pool-ai-opinion-reason-consistency-proof

`managed-pool-ai-opinion-reason-consistency-proof` verifies that fresh Managed
Pool AI opinion overlays do not leak stale/manual-required fallback copy into
the user-facing `reason` or `next_action`.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-reason-consistency-proof --fixture fresh-data-insufficient-stale-reason
```

PASS requires `stale_reason_leaked=false`,
`stale_next_action_leaked=false`, `stale_reason_replaced=true` for the fresh
stale-reason fixture, `reason_consistent_with_freshness=true`,
`provider_external_call_count=0`, `order_execution=false`,
`final_action_unchanged=true`, `actual_order=false`, and
`managed_pool_mutation=false`. The manual refresh and target-symbol E2E proofs
also expose `fresh_overlay_tooltip_sample` so the target overlay sample is not
confused with the generic table tooltip sample collected during dry reads.

### manual-ai-refresh-target-symbol-e2e-proof

`manual-ai-refresh-target-symbol-e2e-proof` verifies that the manual Managed
Pool AI refresh path keeps the selected table row symbol aligned end to end:
selected row symbol, dedicated opinion payload symbol, and overlay symbol must
match.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode manual-ai-refresh-target-symbol-e2e-proof --target-symbol KRW-ETH --provider local --observe-only
```

The report records the selection owner, resolver owner, table object name,
`target_symbol`, `selected_symbol`, `payload_symbol`, `overlay_symbol`,
`target_match`, `fallback_used`, `dedicated_payload_used`,
`overlay_applied_to_target_only`, and `changed_overlay_symbols`. PASS requires
`fallback_used=false`, the three symbols to match, overlay changes limited to
the target symbol, provider call count `0` for LOCAL, and no order execution,
final-action change, or Managed Pool mutation.

### live-on-runtime-e2e-diagnostic

The ON runtime E2E diagnostic is covered by:

- `live-on-runtime-e2e-diagnostic-dryrun`
- `live-on-runtime-e2e-diagnostic-log-summary`

Examples:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-runtime-e2e-diagnostic-dryrun --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-runtime-e2e-diagnostic-log-summary --observe-only
```

These modes emit `aits_live_on_runtime_e2e_diagnostic_v1`. They read recent
runtime smoke reports and `data/logs/aits.log`; they do not click AITS ON, do
not require `--target-symbol`, do not force a candidate, and do not call
providers, Router, RiskGuard, LivePreflight, ExecutionBridge, OrderService, or
OrderAdapter.

Runtime diagnostics must keep fixture symbols separate from live runtime
symbols. The report uses `detected_candidate_symbol` only when the app's own
runtime logs or recent reports reveal one. If no candidate is visible, it
reports `first_blocker`, `all_blockers`, `last_reached_stage`, and
`next_fix_target` instead of injecting a symbol.

PASS means the diagnostic report was generated safely. It is not order
permission. The safety fields remain `provider_external_call_count=0`,
`managed_pool_mutation=false`, `actual_order_forced=false`,
`forced_candidate_injected=false`, and `forced_symbol_configured=false`.

### live-on-preflight-krw-balance-source-summary

`live-on-preflight-krw-balance-source-summary` reads recent
`[AITS][KRWBalanceSource]` and `[AITS][LiveOnPreflight]` logs to classify why
ON preflight saw `available_krw=0`.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-krw-balance-source-summary --observe-only
```

The mode emits `aits_live_on_preflight_krw_balance_source_summary_v1` with
`balance_status`, `balance_source`, `balance_fetch_attempted`,
`balance_fetch_success`, `balance_fetch_error_type`,
`upbit_private_connected`, `fallback_reason`, `first_blocker`, and
`next_fix_target`. It does not call order submit paths and keeps
`provider_external_call_count=0` and `submitted_count=0`.

### live-on-preflight-effective-cap-summary

`live-on-preflight-effective-cap-summary` reads recent ON preflight logs and
verifies the effective cap calculation.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-effective-cap-summary --observe-only
```

The mode emits `aits_live_on_preflight_effective_cap_summary_v1` with
`available_krw`, `order_amount_krw`, `position_policy_mode`,
`user_pos_limit_applied=false`, `pos_limit_krw=null`,
`per_order_hard_cap_krw`, `total_guarded_window_cap_krw`,
`effective_hard_cap_krw`, `first_blocker`, and `can_on_preflight_pass`. It does
not change settings or place orders.

### asset-position-policy-inheritance-summary

`asset-position-policy-inheritance-summary` verifies the read-only asset
override vs AI dynamic position contract. Asset `0%` or missing means AI
dynamic mode, not global inheritance and not a zero position limit.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode asset-position-policy-inheritance-summary --observe-only
```

The mode emits `aits_asset_position_policy_ai_dynamic_summary_v1` with
`asset_pos_size_pct`, `asset_zero_means_ai_dynamic`, `asset_policy_mode`,
`user_pos_limit_applied`, `user_pos_limit_krw`, fixture results, and safety
flags.

### asset-position-policy-ai-dynamic-summary

`asset-position-policy-ai-dynamic-summary` is the explicit name for the same AI
dynamic policy contract.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode asset-position-policy-ai-dynamic-summary --observe-only
```

### live-on-preflight-ai-dynamic-cap-summary

`live-on-preflight-ai-dynamic-cap-summary` verifies that ON-start preflight has
no candidate symbol and excludes user position cap from effective cap.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-ai-dynamic-cap-summary --observe-only
```

### live-on-preflight-position-policy-source-summary

`live-on-preflight-position-policy-source-summary` verifies that the ON start
preflight is symbol-less and uses `ai_dynamic_pending_candidate`, while a later
candidate/order preflight may apply a positive asset override.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-position-policy-source-summary --observe-only
```

It emits `aits_live_on_preflight_position_policy_source_summary_v1` and keeps
`actual_order=false`, `submitted_count=0`, and `provider_external_call_count=0`.

### upbit-accounts-readonly-krw-parse-proof

`upbit-accounts-readonly-krw-parse-proof` verifies `/v1/accounts` KRW row
parsing with mock responses only. It does not call Upbit.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-krw-parse-proof --observe-only
```

The mode emits `aits_upbit_accounts_readonly_krw_parse_proof_v1` with fixture
results for positive KRW, locked KRW, missing KRW row, invalid numeric values,
empty accounts, HTTP 401, and HTTP 403. Safety fields remain
`provider_external_call_count=0`, `private_order_call_count=0`, and
`submitted_count=0`.

### upbit-accounts-readonly-balance-fetch-diagnostic

`upbit-accounts-readonly-balance-fetch-diagnostic` inspects the secret-safe
Upbit accounts read path. By default it checks key presence, short key
fingerprint, and local JWT build readiness without calling `/v1/accounts`.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-balance-fetch-diagnostic --observe-only
```

An actual read-only accounts call requires explicit operator intent:

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode upbit-accounts-readonly-balance-fetch-diagnostic --allow-upbit-readonly-accounts-call --observe-only
```

The mode emits `aits_upbit_accounts_readonly_balance_fetch_diagnostic_v1`.
Order endpoints remain forbidden.

### live-on-runtime-after-preflight-stage-trace

`live-on-runtime-after-preflight-stage-trace` and
`live-on-runtime-after-preflight-stage-summary` classify the latest ON logs
after preflight. They separate UI ON, preflight pass/fail, runtime start
request, runner start, order gate, live gate, order intent reachability, and
submit reachability.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-trace --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-runtime-after-preflight-stage-summary --observe-only
```

The modes emit `aits_live_on_runtime_after_preflight_stage_trace_v1` and do not
call RiskGuard, LivePreflight, unlock, ExecutionBridge, OrderService,
OrderAdapter, provider APIs, or exchange order endpoints.

`AITS-LIVE-ON-BUTTON-ACTIVE-HANDLER-INSTRUMENTATION-01` extends this parser
with active handler markers: `on_handler_enter_detected`,
`preflight_start_detected`, `preflight_result_detected`,
`runtime_start_result_detected`, `runtime_stop_requested`,
`runtime_stop_result_detected`, `execution_mode_before`,
`execution_mode_after`, `order_allowed_before`, `order_allowed_after`,
`real_order_before`, and `real_order_after`.

### runtime-provenance-log-summary

`runtime-provenance-log-summary` reads recent runtime logs and verifies which
code/build and ON widget are active.

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode runtime-provenance-log-summary --observe-only
```

The mode emits `aits_runtime_provenance_log_summary_v1` with
`runtime_provenance_detected`, `app_gui_file`, `instrumentation_id`,
`git_head_detected`, `frozen`, `on_widget_bound_detected`,
`on_widget_object_name`, `clicked_probe_detected`, `toggled_probe_detected`,
and `handler_enter_detected`. It is log analysis only and does not call
RiskGuard, LivePreflight, OrderService, OrderAdapter, provider APIs, or order
endpoints.

The parser uses the latest `RuntimeProvenance app_start` line as the session
boundary. Probe lines before that timestamp are ignored and reported as
`old_probe_ignored_count`; fresh-session fields are exposed as
`fresh_clicked_probe_detected`, `fresh_toggled_probe_detected`,
`fresh_handler_stage_detected`, and `handler_stage_sequence`.

The ON stage parser also reports `handler_toggled_stage_detected`,
`handler_impl_stage_detected`, and `handler_run_stage_detected`. Fresh
click/toggle probes without a handler stage are classified as
`on_signal_not_connected_to_handler`; later gaps are classified by the missing
forwarding stage.

Bridge diagnostics include `bridge_connected_flag`, `bridge_widget_id`,
`signal_widget_id`, and `bridge_connection_suspected_failed`. The active
StopButton handler path uses stored single-entry slots for `toggled` and
`clicked`; the slot logs the probe, dedupes paired signals, records the
bridge/wrapper stage sequence, and forwards once into the existing runtime
handler.
The after-preflight summary reads `runtime_status_display` as `ui_on_state` so
the harness can distinguish OFF, blocked, and observing states without treating
that display as order permission.
It also parses `_on_toggle_run` branch traces: `run_branch`, early returns,
preflight exceptions, `start_blocked`, `start_requested`, and `start_result`.
This separates signal wiring failures from provider/preflight/runtime-start
blockers.

### live-on-runtime-harness-driven-click-run

`live-on-runtime-harness-driven-click-run` starts the GUI from the project
workspace, finds `btn_run_toggle`/`StopButton`, clicks it once, waits ten
seconds, then reuses the runtime provenance, after-preflight, and E2E parsers.
It emits `aits_live_on_runtime_harness_driven_click_run_v1`.

The mode is a harness-driven ON verification only. It does not create paper
orders, does not fake balance or caps, and treats any submitted count or order
adapter/service/execution reach as critical.

## 2026-07-08 ON Provider Readiness Auto-Check Modes

- `live-on-preflight-provider-ready-regression-proof` now covers connected, failed, key-missing, auto-check-disabled, auto-check-success, auto-check-failure, cross-provider isolation, and Local readiness cases.
- `live-on-runtime-harness-driven-click-run` keeps provider readiness calls disabled and may preserve `provider_connection_check_needed`.
- `live-on-runtime-harness-driven-click-run-provider-check-once` installs a mock one-shot provider readiness check. It allows at most one provider readiness call marker, keeps submitted/order paths at zero, and verifies the next blocker moves past provider readiness when the mock check succeeds.
## 2026-07-08 - ON Runtime Feed/Balance SSOT Fields

- `live-on-runtime-e2e-diagnostic-log-summary` now reports runtime market-feed readiness from `RuntimeFeedReadiness` first, then latest-session `CandidateFeedState`, `top_markets_return`, `tickers_return`, and `NetworkState`.
- New feed fields include `market_feed_source`, `market_feed_reason`, `market_feed_blocker`, `latest_candidate_feed_total`, `latest_candidate_feed_buy_ready`, `latest_top_markets_count`, `latest_tickers_count`, and `latest_network_status`.
- Balance/cap fields are parsed from `LiveOnPreflight` and `KRWBalanceSource`: `balance_gate_detected`, `available_krw`, `accounts_fetch_status`, `balance_fallback_reason`, `effective_cap_krw`, and `balance_gate_blocker`.
- Harness diagnostics must keep `actual_order=false`, `submitted_count=0`, and must not synthesize market feed or balance values.

## 2026-07-08 - Public Market Feed Diagnostic Mode

- Added `public-market-feed-diagnostic` as a read-only public market diagnostic wrapper around the top-markets feed proof.
- The mode reports `diagnostic_status=ok|degraded`, `public_feed_failure_type`, `empty_reason`, `exception_type`, `error_message_sanitized`, market/ticker counts, and safety flags.
- A degraded public feed still exits as harness PASS when the diagnostic is produced; trading/order safety remains enforced separately.
- E2E summaries ignore pre-session top-market proof successes when a newer RuntimeProvenance session exists.
- Public feed diagnostics must keep `actual_order=false`, `submitted_count=0`, provider trading calls disabled, and no fake market rows.

## 2026-07-08 - Public Feed Network Profile Proof

- Added `public-market-feed-network-profile-proof` to compare public feed reachability across harness process, direct service call, recent app runtime logs, and latest external/escalated public diagnostic reports.
- The mode emits `aits_public_market_feed_network_profile_proof_v1` with per-profile `python_executable`, `cwd`, `frozen`, `git_head`, market/ticker/top counts, exception fields, elapsed time, and safety flags.
- If the harness process fails but the observed app runtime public profile succeeds, the report sets `runtime_network_profile_split_detected=true`.
- A successful external/escalated public read is reported separately as endpoint reachability evidence; it does not clear an app runtime feed blocker by itself.
- The proof remains read-only public market data only: no provider trading calls, no private balance mutation, no order path.

## 2026-07-08 - Real User App Public Feed Profile Summary

- Added `real-user-app-public-feed-profile-summary` for log-only analysis of a user-launched app session.
- This mode never starts `run.py`, never clicks ON, and never performs provider/order calls. It reads the latest `RuntimeProvenance` session from existing logs.
- Output separates `harness_process_network_ok`, `observed_app_process_network_ok`, `user_app_process_network_ok`, and `external_public_read_network_ok`.
- `profile_split_result` values include `user_app_ok_harness_restricted`, `user_app_and_harness_both_restricted`, `no_user_app_session_detected`, `harness_launched_app_session_detected`, and `external_ok_all_local_restricted`.
- E2E diagnostics can use `market_feed_user_app_ok=true` to avoid pinning a harness-only `market_feed_network_error` to the user runtime profile.

## 2026-07-08 - ON Runtime Start And Order Intent Candidate Contract

- `live-on-runtime-e2e-diagnostic-log-summary` and `live-on-runtime-after-preflight-stage-summary` now read runtime start from `[AITS][RuntimeState]` instead of broad live/feed tokens.
- New summary fields include `runtime_start_source`, `runtime_start_reason`, `runtime_start_result`, `candidate_loop_source`, `latest_buy_ready_count`, `order_intent_candidate_reason`, `order_intent_candidate_blocker`, and `order_intent_candidate_observe_only`.
- `[AITS][OrderIntentCandidate]` is observe-only in this phase. It may prove that a Buy Ready row is contract-shaped, but it must leave Router, RiskGuard, LivePreflight, ExecutionBridge, OrderService, OrderAdapter, submit, and real-order flags false.
- The harness now reports `start_request_count`, `start_skipped_reason`, and `duplicate_suppressed_count`, and applies a false-positive guard so `*_called=False` text is not counted as an actual call.

## 2026-07-08 - RouterHandoff Preview Parser

- The harness recognizes `[AITS][RouterHandoff] event=handoff_preview` as `aits_router_handoff_preview.v1`.
- Preview-only handoff is reported through `router_handoff_preview_detected`, `router_handoff_request_id`, `router_handoff_symbol`, `router_handoff_side`, `router_handoff_amount_krw`, `router_apply`, `final_action_applied`, and `router_validation_observe_only`.
- `RouterHandoff` preview lines do not count as `router_called`; DecisionRouter validation/final-action logs remain separate.
- If preview exists without Router validation, summaries report `router_handoff_preview_only` and keep all submit/order-path fields at zero/false.

## 2026-07-08 - RouterValidation Preview Parser

- The harness recognizes `[AITS][RouterValidation] event=validation_preview` as `aits_router_validation_preview.v1`.
- New fields include `router_validation_preview_detected`, `router_validation_schema`, `router_validation_request_id`, `router_validation_source_request_id`, `router_validation_status`, `router_validation_input_valid`, `router_validation_action_preview`, `router_validation_confidence_preview`, `router_validation_blocker`, and `router_validation_next_fix_target`.
- A passed validation preview reports `first_blocker=router_validation_observe_only`; it is still no-apply and must not call RiskGuard, LivePreflight, ExecutionBridge, OrderService submit, or OrderAdapter.
- `[AITS][OrderService] fetch_accounts called` is parsed separately as `order_service_readonly_accounts_called` and no longer counts as `order_service_reached`.

## 2026-07-08 - RiskGuard/LivePreflight Preview Parser

- The harness recognizes `[AITS][RiskGuardPreview] event=risk_preview` and `[AITS][LivePreflightPreview] event=live_preflight_preview`.
- New fields include `riskguard_preview_detected`, `riskguard_preview_status`, `riskguard_preview_blocker`, `riskguard_apply`, `live_preflight_preview_detected`, `live_preflight_preview_status`, `live_preflight_preview_blocker`, `live_preflight_apply`, and `unlock_performed`.
- Preview false markers such as `riskguard_apply=False`, `live_preflight_apply=False`, and `unlock_performed=False` are not treated as calls.
- The next blocked stage becomes `riskguard_preview_blocked`, `live_preflight_preview_blocked`, or `live_preflight_preview_observe_only` while submit/order fields remain zero/false.

## 2026-07-08 - GuardedExecutionContract Parser

- The harness recognizes `[AITS][GuardedExecutionContract] event=contract_preview`.
- New fields include `guarded_execution_contract_detected`, `guarded_execution_contract_schema`, `guarded_execution_request_id`, `guarded_execution_symbol`, `guarded_execution_side`, `guarded_execution_amount_krw`, `confirm_phrase_required`, `confirm_phrase_matched`, `unlock_required`, `unlock_performed`, `execution_allowed`, and `next_required_user_action`.
- A contract with `live_order_approval_required=True` and `execution_allowed=False` is reported as `first_blocker=live_order_approval_required`.
- This parser treats the contract as pre-execution visibility only; execution, order service, order adapter, submit, or actual-order markers remain critical.

## 2026-07-08 - Guarded Live Order Readiness Summary

- Added `live-order-guarded-readiness-summary`.
- The mode never submits. It summarizes current guarded approval logs and runs a direct contract proof for blocked and approved states.
- A blocked proof must keep `execution_allowed=false` without confirm phrase and unlock.
- An approved proof may set `execution_allowed=true` only when exact phrase, valid unlock, `amount_krw=10000`, caps, and zero submit counts are present.
- Any actual submit must be performed later by explicit user UI action, not by the harness.
- The mode also reports the restored UX fields `live_order_ux_ready`, `approval_dialog_opened`,
  `confirm_phrase_validated`, `confirm_phrase_rejected`,
  `live_order_button_header_removed`, and `on_button_layout_restored`.
- Live trading visibility fields include `live_monitoring_started`,
  `approval_waiting_status_detected`, `approval_waiting_reason`,
  `approval_dialog_auto_opened`, `approval_dialog_input_visible`,
  `approval_button_enabled`, and `live_order_ux_silent_failure`.

## 2026-07-08 - Normal ON Auto-Trading Parser

- `live-on-runtime-e2e-diagnostic-log-summary` and
  `live-on-runtime-after-preflight-stage-summary` now parse
  `[AITS][LiveOrderPipeline]` normal-flow events.
- Normal-flow fields include `normal_live_order_pipeline_detected`,
  `live_pipeline_candidate_selected`, `live_pipeline_router_result`,
  `live_pipeline_riskguard_result`, `live_pipeline_execution_requested`,
  `live_pipeline_execution_result`, `live_pipeline_order_submit_result`, and
  `live_pipeline_blocker`.
- A normal guarded-window flow does not require one-shot unlock lines. Submit
  still requires RiskGuard, LivePreflight, ExecutionBridge, OrderService, and
  OrderAdapter evidence, and duplicate/retry detection remains critical.
## 2026-07-08 - Buy Ready Criteria Summary Fields

- `live-on-runtime-after-preflight-stage-summary` and `live-on-runtime-e2e-diagnostic-log-summary` parse the new buy-ready visibility logs.
- New parsed fields include `buy_ready_criteria_detected`, `managed_candidate_evaluated_count`, `best_candidate_symbol`, `best_candidate_score`, `best_candidate_status`, `best_candidate_blocker`, `buy_ready_threshold`, `no_candidate_reason`, `live_pipeline_no_candidate_detected`, and `user_visible_candidate_status`.
- A normal ON run with no candidate should report `event=no_candidate`, keep `submitted_count=0`, keep `actual_order=false`, and preserve Router/RiskGuard/LivePreflight/Execution boundaries.

## 2026-07-08 - LIVE LOG UX Summary Fields

- `dry-read` reports the central LIVE LOG contract without touching trading paths.
- New fields include `bottom_raw_status_removed`, `live_log_repositioned_to_main_top`, `live_log_latest_visible`, `live_log_latest_message`, `live_log_recent_count`, `live_log_recent_popup_supported`, `live_log_animation_supported`, `common_settings_live_log_integrated`, `common_settings_live_log_count`, `live_log_korean_message_detected`, and `live_log_silent_failure`.
- The common-settings right-side log is a mirror of the same in-memory LIVE LOG buffer, not a separate source of truth.
- These checks are UI/diagnostic only and must keep `submitted_detected=false` and `order_risk_detected=false`.
### Runtime contract and log retention fields

`live-on-runtime-after-preflight-stage-summary` and
`live-on-runtime-e2e-diagnostic-log-summary` parse
`[AITS][RuntimeContract]` logs. Reports include:

- `runtime_contract_active`
- `runtime_contract_reason`
- `runtime_contract_last_writer`
- `candidate_blocked_by_runtime_contract_count`
- `buy_ready_but_runtime_contract_inactive_count`
- `provider_ready_mismatch_count`
- `heartbeat_expected`
- `heartbeat_detected`
- `heartbeat_missing_reason`
- `log_retention_policy_detected`
- `log_retention_estimated_hours`

The development `run.py` logger retains larger rotated logs so 6-8 hour ON
observations can be reviewed after the app is stopped.
## Normal Live Pipeline Fields

`live-on-runtime-e2e-diagnostic-log-summary` reads the retained AITS logs, including rotated logs, with a larger default log window so early ON pipeline events are not lost during long runs.

Additional fields:

- `router_validation_started`
- `router_validation_result_detected`
- `router_validation_status`
- `router_validation_action`
- `duplicate_candidate_locked_count`
- `duplicate_candidate_lock_ttl_sec`
- `candidate_allowed_after_duplicate_lock`
- `live_pipeline_live_preflight_started`
- `live_pipeline_live_preflight_result`

The harness must not classify a normal live flow as `candidate_selected_but_router_not_started` when `[AITS][LiveOrderPipeline] event=router_validation_started` or `event=router_validation_result` exists in the retained log window.

## Post-Submit Reconciliation Summary

`live-order-post-submit-reconciliation-summary` is a read-only log summary mode.
It audits submitted live order request ids, TradeLog reflection evidence, holdings
refresh evidence, InvestmentCenter position reflection, available KRW delta,
duplicate submit markers, and retry markers.

The mode does not start the app, click ON, call providers, or submit orders.

## Candidate Holdings Guard Fields

`live-on-runtime-e2e-diagnostic-log-summary` and `live-on-runtime-after-preflight-stage-summary` parse add-position guard logs without placing orders. The parser distinguishes held-symbol add-position candidates from new-entry candidates and exposes allow/block reason fields for long-run observation, including `expected_weight_after_order`, `candidate_order_amount_krw`, and `candidate_total_asset_estimate`.

`live-order-post-submit-reconciliation-summary` reports latest-order reflection
fields separately from historical gaps: `latest_live_order_request_id`,
`latest_live_order_symbol`, `latest_trade_log_reflected`,
`latest_holdings_refreshed`, `latest_position_reflected`, `latest_reflection_ok`,
and `historical_reflection_missing_count`.

## Account / Position Reconciliation Fields

The long-run summaries and `live-order-post-submit-reconciliation-summary` parse
read-only account reflection evidence:

- `top_pnl_krw`, `top_pnl_pct`, `top_pnl_source`, `top_pnl_status`
- `actual_trade_log_count`, `actual_trade_filter_count`, `actual_trade_symbols`
- `investment_position_symbols`, `investment_position_format_ok`
- `investment_total_pnl_krw`, `investment_total_pnl_pct`
- `external_exchange_sync_detected`
- `external_position_change_candidate_count`

Actual trade rows must come from submitted live-order evidence or read-only
exchange reconciliation. The harness must not create synthetic trades,
synthetic holdings, synthetic PnL, or submit orders while producing these
summaries.
## Add-position policy summary fields

The runtime smoke harness reports add-position safety evidence from
`[AITS][AddPositionPolicy]`.

Important fields:
- `expected_weight_after_order`
- `max_position_weight_pct`
- `symbol_add_position_cooldown_sec`
- `seconds_since_last_symbol_buy`
- `symbol_window_amount_krw`
- `symbol_window_cap_krw`
- `global_window_amount_krw`
- `global_window_cap_krw`
- `add_position_cooldown_blocked`
- `add_position_weight_cap_blocked`
- `add_position_window_cap_blocked`
- `bera_repeated_buy_policy_verdict`

Default safety policy:
- same-symbol add-position cooldown: 3600 seconds
- dynamic max position weight: 30.0%
- same-symbol 6h add-position amount cap: 20000 KRW
- global 6h add-position amount cap: 40000 KRW

The harness must report these as observation fields only. It must not click ON,
submit orders, create synthetic holdings, or mutate runtime state during observe-only
summary modes.
## LIVE LOG Inline History UX

- MAIN ANALYSIS CENTER의 LIVE LOG는 클릭 시 팝업을 열지 않고 같은 영역 아래에서 최근 5개 운용 로그를 inline으로 펼친다.
- inline history와 공통설정 운용 로그는 `message_ko`만 표시하며 `raw_event`, snake_case blocker, 개발용 이벤트명은 사용자-facing 텍스트로 노출하지 않는다.
- 공통설정 운용 로그는 최근 50개 전체 히스토리, MAIN ANALYSIS CENTER inline history는 최근 5개 빠른 확인용, 매매기록 탭은 실제 체결/AI 판단/차단 기록용이다.
- dry-read는 `live_log_inline_expand_supported`, `live_log_popup_disabled`, `live_log_snake_case_leak_count`, `common_settings_live_log_korean_only`, `live_log_blocker_koreanized`를 보고한다.

## Managed Pool Holdings Must Include

- 실제 holdings/account/position snapshot에서 수량이 0보다 큰 종목은 Managed Pool에 반드시 포함되어야 한다.
- TradeLog actual order row는 보조 evidence이며, 단독으로 holding source row를 만들지 않는다.
- `managed-pool-holdings-include-summary`는 current holdings symbols와 saved managed pool symbols를 비교해 누락, source/protected, max-count override 여부를 보고한다.
- 보유 종목은 `source_type=live_holding`, `holding=True`, `protected=True`로 표시되며 max managed count보다 우선한다.
## Managed Pool Rotation Score SSOT

- Managed Pool rotation is observe-only in this stage.
- Score roles are separated:
  - `operating_score`: current Managed Pool operation score.
  - `scanner_score`: right-side scanner candidate score.
  - `normalized_rotation_score`: 0-100 comparison score used only for rotation planning.
- Holding/protected rows are excluded from rotation-out candidates.
- Non-holding rows can become rotation-out candidates only when a new scanner candidate passes `min_promotion_score=65` and `rotation_margin=8`.
- The default rotation preview is capped to `max_rotation_per_cycle=1` and `rotation_cooldown_sec=3600`.
- Harness fields include `rotation_logic_detected`, `rotation_score_source`, `normalized_rotation_score_supported`, `rotation_plan_detected`, `rotation_plan_observe_only`, `holding_symbols_excluded_from_rotation`, `protected_symbols_excluded_from_rotation`, `managed_pool_count_mode`, and `rotation_blocker`.
- `managed_pool_mutation` must remain false in observe-only summaries.

## Managed Pool active monitor status bar

- The managed pool panel shows a compact Korean status bar near the managed symbols table.
- The status bar is for current state only: managed count, max count, holding count, rotation preview/no-target state, and order state.
- LIVE LOG remains the event history surface; the managed pool status bar must not open popups or replace LIVE LOG inline history.
- User-facing text must be Korean only and must not expose raw event names, snake_case blockers, `submitted_count`, `actual_order`, or mutation flags.
- The status bar is observe-only UI. It must not place orders, apply rotation, mutate the managed pool, or bypass any trading guard.
- Harness fields: `managed_pool_status_bar_detected`, `managed_pool_status_bar_text`, `managed_pool_status_bar_korean_only`, `managed_pool_status_bar_no_raw_event_leak`, `managed_pool_status_bar_state`, managed/max/holding counts, rotation state, and order state.
## Managed Pool dust holdings and weight target SSOT

- Managed Pool auto-include protects manageable live holdings, not every positive quantity row.
- `dust_holding` means a balance exists but its KRW valuation is below the managed holding threshold. It is logged and summarized, but it is not automatically restored into Managed Pool.
- Defaults: `dust_threshold_krw=5000`, `managed_holding_min_value_krw=10000`.
- Dust holdings are observe/log only. AITS must not trigger sell actions or create synthetic holdings or valuation data to clear dust.
- Manageable holdings remain protected and monitored for loss/profit/rotation risk.
- The Managed Pool weight/target column uses current position value divided by total asset when available. If the source is unavailable, display `-` rather than `0%`.
- Target weight priority is user symbol target, then AI/suggested target, then policy target. If no source exists, display `-` rather than defaulting to `0%`.
- Harness fields include dust symbols, excluded/readded dust symbols, manageable holding symbols, weight/target zero-zero count, nonzero holding weight count, and source fields for weight/target.

## Live Buy Total Cap And Sell Observe Diagnostics

- `risk_budget.total_budget_krw` is the live buy total exposure cap when it is greater than zero.
- Buy exposure is evaluated from actual buy cost and manageable live position value. If both exposure and total asset sources are unavailable, live buy is blocked.
- A live buy with `total_asset_krw=0` must not be treated as allowed.
- `[AITS][TotalOperatingCap]` logs cap source, projected exposure, remaining cap, and the blocker before Router/RiskGuard/LivePreflight.
- Sell/take-profit evaluation is observe-only in this stage. It may report `sell_preview_only` and take-profit candidates, but it must not submit sell orders.
- The status bar separates cycle state from cumulative state: current cycle order status and today's cumulative buy/sell counts are distinct fields.
- Harness fields include `total_operating_cap_detected`, `total_operating_cap_krw`, `projected_exposure_after_buy`, `live_buy_blocked_by_total_cap`, `sell_evaluation_called`, `take_profit_candidate_symbols`, `sell_preview_only`, `side_sell_submit_count`, and cumulative order counters.

## External Holdings Adoption And Emergency Stoploss Observe

- A live account holding that is not known by AITS actual-order evidence is classified as `source_type=external_holding` when its KRW valuation is at or above `managed_holding_min_value_krw`.
- External holdings remain dust-filtered by the same policy as other holdings. Dust external rows are logged as `external_holding_dust_excluded` and are not restored to Managed Pool.
- Manageable external holdings are adopted into Managed Pool with `holding=True`, `protected=True`, `managed_protected=True`, `origin=upbit_account_snapshot`, and status `외부보유관리`.
- External holdings use the sell observe path. PnL source priority is account average price plus current price, position snapshot, then sufficient managed holding valuation.
- Stop-loss thresholds are watch at `-5%`, candidate at `-10%`, and emergency candidate at `-20%`.
- This stage is preview-only. Emergency stop-loss can produce logs, LIVE LOG, and status-bar warnings, but it must not submit a sell order.
- Harness fields include `external_holding_detection_supported`, `external_holding_symbols_detected`, `external_holding_symbols_adopted`, `external_holding_symbols_dust_excluded`, `external_holding_pnl_source_missing_symbols`, `stop_loss_candidate_symbols`, `emergency_stop_loss_candidate_symbols`, `emergency_stop_loss_preview_only`, `external_holding_sell_submit_count`, and `actual_sell_order_count`.

## ON Preflight Buy-Blocked Monitor-Only

- ON preflight separates runtime fatal blockers from buy blockers.
- Runtime fatal blockers still prevent ON. Examples include provider/account connection failure, invalid keys, and system preflight exceptions.
- Buy blockers do not prevent ON. Examples include `insufficient_available_krw`, total operating cap exceeded, effective cap below minimum order, add-position cooldown, and weight/window caps.
- When only a buy blocker is present, AITS starts as monitor-only: `runtime_monitor_only_mode=True`, `buy_enabled=False`, `buy_blocked=True`, and sell observe remains enabled.
- Buy-blocked monitor-only mode must not submit buy or sell orders. It may continue holdings monitoring, PnL updates, take-profit previews, stop-loss previews, and external holding adoption.
- Harness fields include `on_preflight_buy_blocker_nonfatal`, `on_preflight_runtime_fatal_blocker`, `on_allowed_with_insufficient_available_krw`, `runtime_monitor_only_mode`, `buy_enabled`, `buy_blocked`, `buy_blocker`, `sell_observe_enabled_while_buy_blocked`, `status_bar_buy_blocked_monitoring_message`, `live_log_buy_blocked_monitoring_message`, and submit counters after buy-block.

## Holding Sell Observe Loop

- Monitor-only ON runtime must call the holding sell observe loop from the existing runtime heartbeat/status cycle.
- `[AITS][SellEvaluation]` records `sell_eval_cycle_started`, per-position `sell_eval_position`, preview events, and `sell_eval_cycle_completed`.
- PnL source missing is logged as an evaluated result, not silently skipped.
- Harness fields include `sell_eval_cycle_count`, `sell_eval_position_count`, `take_profit_watch_symbols`, `strong_take_profit_candidate_symbols`, `stop_loss_watch_symbols`, and `sell_eval_runs_while_buy_blocked`.
- The loop is observe-only: `preview_only=True`, `actual_order=False`, `submitted=0`; sell submit requires a separate approved execution Goal.

## Active Heartbeat SellEvaluation Probe

- The active runtime heartbeat path must emit `[AITS][SellEvaluation] event=sell_eval_heartbeat_probe`.
- A skipped probe is different from a missing connection. Harness fields distinguish `sell_eval_heartbeat_probe_detected`, `sell_eval_heartbeat_result_detected`, and `sell_eval_heartbeat_skipped_detected`.
- Buy-blocked monitor-only mode is a valid state for sell observation. `buy_blocked=True` must not suppress SellEvaluation.
- If manageable holdings exist but no position is evaluated, E2E reports `managed_holdings_not_passed_to_sell_evaluation`.
- Any actual sell submit remains a critical failure in this observe-only stage.

## Actual Log Writer SellEvaluation Anchor

- Candidate feed score updates are an active runtime writer for monitor-only observation.
- The writer emits sell_eval_actual_writer_probe, then sell_eval_actual_writer_result or sell_eval_actual_writer_skipped.
- Harness fields include sell_eval_actual_writer_probe_detected, sell_eval_actual_writer_result_detected, sell_eval_actual_writer_skipped_detected, sell_eval_actual_writer_name, and sell_eval_actual_source_event.
- The anchor remains observe-only and must report `actual_order=False` and `submitted=0`.

## Guarded Sell Apply V1

- SellEvaluation can promote take-profit or stop-loss candidates to guarded sell apply candidates during an active ON runtime.
- Thresholds such as take-profit at 4%, strong take-profit at 5%, stop-loss at -10%, and emergency stop-loss at -20% are AI decision triggers, not direct BASIC sell authority.
- Sell ratios are applied only when the AI decision output explicitly chooses sell, reduce, take_profit, or stop_loss.
- Every sell apply must pass RiskGuard and LivePreflight before reaching ExecutionBridge, OrderAdapter, and OrderService.
- Harness fields include `sell_apply_supported`, `sell_apply_candidate_symbols`, `sell_intent_created_count`, `sell_guard_passed_count`, `sell_preflight_passed_count`, `sell_submit_requested_count`, `side_sell_submit_count`, `actual_sell_order_count`, `sell_trigger`, `sell_ratio`, `sell_volume`, and `estimated_sell_value_krw`.
- Dry-read and non-active runtime summaries may detect candidates but must block apply with `runtime_not_active_for_sell_apply`.

## AI Decision Authority For Position Management

- BASIC collects position, market, indicator, portfolio, candidate, and constraint data into `aits_ai_decision_payload_v1`.
- Profit/loss thresholds are AI-decision triggers, not direct sell decisions.
- User-facing action authority belongs to GPT, Gemini, or LOCAL AI through `aits_position_management_decision_v1`.
- Harness fields include `ai_decision_payload_created`, `ai_decision_payload_symbols`, `ai_decision_required_count`, `ai_provider_call_requested_count`, `ai_provider_call_blocked_count`, `ai_provider_response_received_count`, `ai_decision_action`, `ai_decision_confidence`, `ai_decision_reason_detected`, `ai_decision_eta_detected`, `fixed_threshold_direct_sell_disabled`, `ai_decision_based_sell_intent_count`, `ai_decision_based_buy_intent_count`, `ai_decision_based_rotate_count`, `local_training_record_created`, and `ai_decision_blocker`.
- If AI decision is required but unavailable, BASIC must not invent a buy/sell action; it reports `ai_decision_required_but_provider_blocked`.

## AI Decision Trigger Role Audit

- `dry-read` reports document and static role-contract audit fields for the AI decision authority contract.
- BASIC role-injection fields include `basic_engine_role_doc_exists`, `basic_engine_role_injected`, `basic_engine_forbidden_actions_documented`, `basic_ai_boundary_documented`, `riskguard_boundary_documented`, `execution_boundary_documented`, `local_training_role_documented`, and `basic_engine_role_contract_ready`.
- AI decision trigger policy fields include `ai_decision_trigger_policy_injected`, `basic_monitoring_cadence_documented`, `ai_event_based_call_policy_documented`, `local_first_policy_documented`, `gpt_gemini_escalation_policy_documented`, `trigger_not_action_policy_documented`, `ai_decision_payload_requirements_documented`, `ai_decision_output_schema_documented`, and `ai_decision_trigger_policy_ready`.
- Harness fields also include `engine_role_contract_doc_exists`, `ai_decision_trigger_policy_doc_exists`, `fixed_threshold_direct_action_detected`, `basic_direct_sell_decision_detected`, `basic_direct_buy_decision_detected`, `ai_decision_payload_path_detected`, `ai_provider_runtime_call_path_detected`, `ai_decision_required_but_not_called_path_detected`, `local_training_record_path_detected`, `decision_record_store_detected`, `role_contract_violation_count`, and `role_contract_violation_samples`.
- The audit is diagnostic only. It does not change order execution, trading decisions, RiskGuard, LivePreflight, or submit paths.

## Engine Role Contract Harness Guard

- `dry-read` reports `engine_role_contract_guard_ready` when the role documents are present and the static guard families are enabled.
- BASIC direct decision scan fields include `basic_direct_trade_decision_static_scan_enabled`, `basic_direct_buy_decision_detected`, `basic_direct_sell_decision_detected`, `basic_direct_rotation_decision_detected`, and `basic_direct_trade_decision_samples`.
- OrderIntent without AI decision scan fields include `order_intent_without_ai_decision_scan_enabled`, `order_intent_without_ai_decision_detected`, `buy_order_intent_without_ai_decision_detected`, `sell_order_intent_without_ai_decision_detected`, `rotation_intent_without_ai_decision_detected`, and `order_intent_without_ai_decision_samples`.
- Trigger-is-not-action guard fields include `trigger_used_as_action_detected`, `trigger_to_action_samples`, `fixed_threshold_direct_action_scan_enabled`, `fixed_threshold_direct_action_detected`, `fixed_threshold_direct_action_samples`, and `threshold_to_action_samples`.
- AI payload/output schema guard fields include `ai_payload_contract_scan_enabled`, `ai_output_contract_scan_enabled`, `ai_decision_payload_builder_detected`, `ai_decision_payload_schema_fields_detected`, `ai_decision_output_schema_detected`, `ai_response_validator_detected`, and `ai_decision_payload_missing_paths`.
- LOCAL training store guard fields include `local_training_contract_scan_enabled`, `local_training_record_path_detected`, `local_training_payload_storage_detected`, `local_training_response_storage_detected`, `local_training_execution_result_storage_detected`, `local_training_outcome_placeholder_detected`, and `local_training_missing_fields`.
- RiskGuard, LivePreflight, and Execution bypass guard fields include `riskguard_bypass_scan_enabled`, `livepreflight_bypass_scan_enabled`, `execution_bypass_scan_enabled`, `riskguard_bypass_detected`, `livepreflight_bypass_detected`, `execution_bypass_detected`, `direct_upbit_order_detected`, `actual_order_hardcode_detected`, `submitted_count_hardcode_detected`, and `bypass_samples`.
- Blocker priority is `execution_bypass_detected`, `direct_upbit_order_detected`, `riskguard_bypass_detected`, `livepreflight_bypass_detected`, `actual_order_hardcode_detected`, `basic_engine_direct_trade_decision_active`, `order_intent_without_ai_decision_detected`, `trigger_used_as_action_detected`, `fixed_threshold_direct_sell_active`, `ai_decision_payload_builder_missing`, `ai_response_validator_missing`, and LOCAL training missing states. The summary fields are `role_contract_violation_count`, `role_contract_violation_types`, `role_contract_violation_samples`, and `role_contract_first_blocker`.

## AI Response Validator And Buy Ready AI Gate

- `validate_ai_decision_response` is the shared AI decision validator contract.
- Required AI output fields are `action`, `confidence`, `reason_ko`, `eta_seconds`, `execution_plan`, `risk_notes`, and `invalidation_conditions`.
- Buy Ready is a trigger, not an action. It must create `task=buy_decision` payload and wait for a validated AI action.
- Buy/add OrderIntent requires AI metadata: `ai_decision_id`, `ai_provider`, `ai_action`, `ai_confidence`, `ai_reason_ko`, `ai_eta_seconds`, `ai_payload_hash`, and `ai_validation_passed=True`.
- If provider response is missing, schema is invalid, or action is hold/wait, no buy OrderIntent is executable and the blocker is recorded.
- Harness fields include `ai_decision_validator_contract_ready`, `ai_decision_validator_required_fields`, `buy_ready_ai_gate_enabled`, `buy_decision_payload_created`, `buy_decision_provider_requested`, `buy_decision_validated`, `buy_order_intent_requires_ai_decision`, `order_intent_ai_metadata_required`, `local_training_buy_decision_record_detected`, and `buy_ai_gate_blocker`.

## Managed Pool Promotion AI Gate

- Managed Pool promotion is an AI decision action because it changes the operating universe before any order is considered.
- BASIC scanner candidates, scanner score, Basic score, and normalized rotation score are promotion triggers, not final promotion authority.
- Automatic `basic_added` rows require AI approval. Approved rows carry promotion metadata and use `source_type=basic_added_ai_approved` or another explicit AI-promoted source.
- `user_added`, `live_holding`, and `external_holding` remain policy exceptions because they represent user intent or real account holdings. Dust exclusion remains a safety filter and does not require AI approval.
- Harness fields include `managed_pool_promotion_ai_gate_enabled`, `promotion_trigger_detected`, `promotion_payload_created`, `promotion_provider_requested`, `promotion_provider_blocked`, `promotion_response_received`, `promotion_validated`, `promotion_allowed_count`, `promotion_blocked_count`, `promotion_ai_metadata_required`, `basic_added_requires_ai_approval`, `basic_added_without_ai_approval_detected`, `managed_pool_promotion_without_ai_decision_detected`, `ai_promoted_symbols`, `promotion_blocker`, and `promotion_training_record_detected`.
- Blockers include `managed_pool_promotion_without_ai_decision`, `promotion_decision_payload_missing`, `promotion_provider_blocked`, `promotion_ai_decision_invalid_schema`, `promotion_rejected_or_wait_by_ai`, and `managed_pool_promotion_ai_gate_ready`.

## Rotation AI Decision Gate

- Rotation is an AI decision action. `normalized_rotation_score` is trigger evidence only.
- Rotation candidates create `task=rotation_decision` payloads and may return `rotate`, `wait`, `hold`, `replace`, `reduce_and_rotate`, or `reject`.
- Protected, user-added, live-holding, and external-holding rows cannot be removed by a simple replacement decision.
- `replace` may prepare a managed-pool universe replacement only when the replace target is removable and AI metadata is present. `rotate` and `reduce_and_rotate` remain `execution_pending` in this stage and do not submit orders.
- Rotation decision records are written for LOCAL training under `rotation_decisions.jsonl`.
- Harness fields include `rotation_ai_gate_enabled`, `rotation_trigger_detected`, `rotation_payload_created`, `rotation_provider_requested`, `rotation_provider_blocked`, `rotation_response_received`, `rotation_validated`, `rotation_allowed_count`, `rotation_blocked_count`, `rotation_ai_metadata_required`, `rotation_without_ai_decision_detected`, `normalized_rotation_score_direct_action_detected`, `rotation_replace_without_ai_approval_detected`, `rotation_execution_pending_count`, `rotation_ai_decision_symbols`, `rotation_blocker`, and `rotation_training_record_detected`.

## ETA And Invalidation ReDecision Scheduler

- `dry-read` reports scheduler, ETA registration/tick/expiry, invalidation, redecision payload/provider/training, and direct-action guard fields.
- ETA expiry and invalidation must create `ai_redecision`; they must not create a direct order, rotation, or managed-pool mutation.
- Provider-blocked outcomes remain non-executable with `actual_order=False` and `submitted=0`.
## ETA Scheduler Runtime Probe And Decision Registration

- `[AITS][ETAReDecision] event=eta_scheduler_probe` proves that the existing runtime active path called the scheduler.
- `event=eta_scheduler_idle` with `reason=no_registered_ai_decision_state` is a healthy idle result, not a scheduler failure.
- Valid buy, position-management sell, promotion, rotation, and redecision responses use the common AI decision runtime-state registration helper.
- Provider-blocked, missing-response, and invalid-schema decisions are not registered as active ETA state.
- Valid `hold`, `wait`, and `reject` decisions remain watchable when they provide ETA or invalidation conditions.
- The E2E summary separates `eta_scheduler_not_called_in_runtime`, `eta_scheduler_running_but_no_registered_ai_decisions`, `ai_decision_registration_missing`, and `eta_tick_not_running`.
- Runtime log analysis anchors on the latest real ON transition when available. PID is reported when provenance is available; logs are not claimed to be PID-filtered unless per-line PID filtering was possible.
## ETA Scheduler Active Callsite Provenance

- The active `CandidateFeedState.score_update` writer records ETA scheduler callsite probe, condition, before-call, after-call, and exception events next to the SellEvaluation call.
- Scheduler internals record entered, idle, and exit events. Zero active decisions is a healthy idle result, not a missing scheduler.
- Runtime diagnostics distinguish a missing callsite, a false call condition, a function that was not entered, idle operation, and an exception.
- The heartbeat contract value and the scheduler's prior self flag are reported separately so last-writer/SSOT mismatches remain visible.
- Holdings/Managed Pool/SellEvaluation target disagreement is not repaired by this instrumentation Goal. Its follow-up is `AITS-HOLDINGS-MANAGED-POOL-SELL-EVAL-TARGET-SSOT-FIX`.
## ON Initial AI Management Seed

- The first active runtime cycle in each ON session creates an AI management seed once.
- Manageable non-dust holdings create `position_management_decision` payloads; the full managed/cash/cap/candidate context creates a `portfolio_management_decision` payload.
- The seed is an AI judgment starting point, never a BASIC action or order intent.
- Provider failures, missing responses, and invalid schemas remain blocked and may retry after the configured cooldown without creating an action.
- Valid hold/wait decisions are registered like other valid decisions so ETA and invalidation monitoring can begin.
- Runtime summaries distinguish trigger, payload, provider request, response, validation, registration, training record, and ETA tick after registration.
## OpenAI Runtime Decision Call Policy

- Provider calls request AI judgment; they do not grant order execution permission.
- Runtime decision tasks use a dedicated provider policy instead of verification one-shot flags.
- OpenAI calls require the selected OpenAI/GPT provider, a resolved masked key, a model, an allowed task, cost capacity, and no duplicate-payload cooldown.
- `runtime_decision_call_requested`, `allowed`, `blocked`, `response_received`, and `response_missing` distinguish policy, transport, and response failures.
- API keys and full prompts are never written to runtime diagnostics. AI responses still require Validator and runtime-state registration before ETA monitoring.
## Runtime Decision State Registration Consistency

- `initial_seed_registered` is valid only when the common runtime store confirms the decision by readback.
- Registration writes and the ETA scheduler read the same `_aits_ai_decision_runtime_states` SSOT.
- Validated `wait` and `hold` decisions with a positive ETA are active watch states.
- Empty invalidation conditions produce `invalidation_condition_missing` but do not block ETA registration.
- The harness distinguishes registration started, store-confirmed, failed, false registered, ETA tick, and ETA waiting.

### Initial Seed Session-Scoped Registration

- Initial-seed registration is aggregated by the latest ON-session `session_id`; it is never compared directly with the cumulative runtime registration count.
- Store consistency is verified by matching the scoped initial-seed decision IDs with store-confirmed `ai_decision_state_registered` events and their ETA registrations.
- ETA scheduler events are evaluated in timestamp order. Idle events before the first registration are normal startup state.
- An idle-after-registration blocker is emitted only when active registration is followed by idle events without any later `eta_tick` or `eta_waiting` event.
- Registration followed by `eta_tick` or `eta_waiting` is reported as `ai_decision_runtime_state_registration_ready`.

### Holdings Target SSOT

- `normalized_manageable_holding_symbols` is the shared target set for the status bar, Managed Pool holding protection, SellEvaluation, and initial position-management payloads.
- Dust holdings remain visible in summary diagnostics but are excluded from Managed Pool recovery, SellEvaluation, and AI position-management targets.
- A manageable holding with missing PnL inputs remains in the target set and reports `pnl_source_missing_for_manageable_holding` as an evaluation blocker.
- Live and external holding recovery is a holding-protection exception to candidate promotion; it never promotes a non-holding candidate.
- The E2E summary compares the normalized, managed, sell-evaluation, and AI-payload symbol sets and reports their exact differences.
## AI Payload Feature Observability And Freshness

- Runtime decision payloads emit an `AIPayloadQuality` feature manifest, payload hash, manifest hash, quality grade, coverage counts, missing features, and stale features.
- The manifest records only safe numeric/state previews. It must not store API keys, account raw data, full prompts, or private response bodies.
- Freshness is explicit: `fresh`, `stale`, or `unknown`. Unknown freshness must never be reported as fresh.
- The runtime summary distinguishes RSI, MACD, volume, volatility, price-change, portfolio-cap, and candidate coverage.
- When an AI reason mentions insufficient data, the harness correlates it with manifest missing/stale features.
- Invalidation results are counted separately as structured objects, natural-language strings, or missing.
## Market Indicator Payload Population Contract

- Position payloads use cached real minute candles and managed-row market data for price changes, volume change, trade value, volatility, RSI, MACD, moving averages, momentum, and trend strength.
- Missing candle history remains missing; the harness must not infer fabricated indicators or freshness.
- `position_management_decision` is canonical. `manage_position_decision` is accepted only as a logged legacy alias and normalized before provider policy validation.
- Portfolio cap fields come from the existing risk-budget and normalized-holdings SSOT.
- Structured invalidation checks report supported and unsupported types separately. Conditions request AI redecision and never become direct actions.

## Invalidation Semantic Mapping And Runtime Scope

- Conditions are normalized from type, category, feature, metric, indicator, and name into watcher trigger types.
- `supported_partial` means the semantic is known but threshold/operator evidence is insufficient; it remains inert until evaluable.
- Missing thresholds never cause immediate redecision, and invalidation conditions never create trading actions directly.
- Live summaries use the latest non-harness runtime PID/session. Dry-read and other harness PIDs are excluded from latest-event aggregation.

## MACD Exists And Status Visibility

- `operator=exists` for MACD registers feature observability only. A present MACD becomes registered-partial and remains non-triggerable without a comparison direction.
- Missing MACD remains watcher-unavailable. Neither case creates a direct action.
- `StatusVisibility` records the same safe Korean candidate text supplied to the status summary or LIVE LOG. It stores no raw event object, prompt, account body, or secret.
- Screen capture remains a separate user-facing verification; the harness validates backend rendering evidence and snake-case leakage.

## Managed Holding Recovery Provenance

- Every normalized manageable holding must be represented in the Managed Pool, even when it appears after startup through an Investment Center or portfolio snapshot.
- The active `CandidateFeedState.score_update` writer periodically runs holding recovery; restore-time and live-account refresh are not its only entrypoints.
- `ManagedPoolRecovery` events distinguish scan, candidate, dust exclusion, applied recovery, later-writer removal, and final consistency.
- Recovered holdings use `managed_holding_recovered` provenance and an explicit holding-recovery exception marker. They are never counted as AI-promoted candidates.
- Actual manageable holdings take precedence over the configured pool size. Dust holdings and non-holding candidates cannot use this recovery path.
- The harness reports BLAST recovery attempt/application, later-writer removal, SellEvaluation/initial-payload membership, and final target-set consistency.

## Holdings Valuation SSOT And Threshold Boundary

- Normalized holdings collect every real valuation candidate before selecting one valuation SSOT. Current-market valuation is preferred over cost basis, then source priority and freshness resolve candidates of the same semantic kind.
- A live account row whose `eval_krw` equals quantity times average buy price is cost basis, not current-market valuation. It remains an alternative audit value and cannot remove a holding selected as manageable by the valuation SSOT.
- Dust and manageable classification use only `selected_valuation_krw`. Alternative dust classifications are warnings, not target-set exclusion reasons.
- A valuation within 100 KRW of `managed_holding_min_value_krw` emits a threshold-boundary audit. The boundary does not change the configured threshold or reverse the selected classification.
- `HoldingsValuationSSOT` events expose collected sources, freshness, conflicts, selected valuation, threshold gap, and final classification. The live summary verifies that Managed Pool, SellEvaluation, and initial AI payload targets remain stable.

## Sell Price/Quantity/Valuation Unit Guard

- Before sell PnL or intent creation, BASIC verifies `selected_valuation_krw` against `qty * current_price`.
- A difference above the larger of 500 KRW or 5 percent marks PnL invalid and blocks sell regardless of the AI action.
- RiskGuard and LivePreflight accept the same mismatch fields as final sell-only defenses. This safety block creates no action.
- `SellUnitGuard` records expected/selected valuation, absolute and relative differences, sources, and `submitted=0` without exposing account or provider secrets.
- Reconciliation aggregates target PID/session events from both `LiveOrderPipeline` and `SellApplyGuard`; an actual submit may never be omitted merely because it used the guarded sell request prefix.

## ETA Redecision Payload Context

- A redecision reuses the initial position or portfolio payload builders instead of constructing a minimal parallel context.
- Position redecisions inherit position, market, indicators, portfolio, candidates, constraints, sell-unit safety, prior decision, ETA, and trigger context. Portfolio redecisions inherit portfolio, candidates, constraints, prior decision, ETA, and trigger context.
- Provider candle population also applies to position-scoped `ai_redecision` payloads. Portfolio-scoped redecisions remain excluded from position candle population.
- `AIReDecisionPayload` events distinguish context start, position/portfolio merge, missing groups, pre-provider score, final provider-populated score, and wait-reason correlation.
- The live harness uses the final time-ordered score and reports whether wait/hold is associated with a data gap or current market conditions.

## Portfolio Redecision Scope And Running PID

- `PORTFOLIO` is a portfolio scope, never a KRW market symbol. Runtime state, ETA registration, and training records use `portfolio_management_decision`, `portfolio_management`, and `portfolio:PORTFOLIO`.
- Position redecisions remain `position_management_decision` with a `position:KRW-*` state key. The original request task is retained separately for provenance.
- The E2E live summary prefers a running, ON, runtime-contract-active non-harness PID. Dry-read report windows and terminated PIDs cannot replace that target.
- Portfolio payload, registration, ETA, and training scope fields are compared explicitly; `KRW-PORTFOLIO` or a position-management registration is a mismatch.

## Portfolio ETA Cadence

- The AI response ETA is retained as `original_eta_seconds`; the scheduler uses a separate `effective_eta_seconds`.
- Portfolio monitoring defaults to a 300-second minimum and a 3600-second maximum. Position ETA behavior is unchanged.
- ETA is a monitoring cadence, not a stop time or an order condition. Portfolio invalidation conditions may request redecision before effective ETA expiry.
- Live summaries require policy evaluation, original preservation, effective registration, and Korean status evidence from the target PID/session.

## Live Operating Cycle v1 Completion Summary

- `live-operating-cycle-v1-completion-summary --observe-only` is the consolidated Sprint check for runtime provenance, target consistency, AI decisions, guards, execution reflection, replanning, training linkage, and UI reasons.
- Structural post-order readiness is checked independently from whether the selected live session happened to submit an order.
- When an actual submit exists, the summary requires reconciliation coverage and reports audited buy/sell counts and missed submits.
- Post-order readiness requires holdings and position refresh, target reconciliation, portfolio replanning, remaining-position reconsideration, ETA registration, and execution-linked outcome evidence.
- The mode never starts the app, changes ON state, requests an action, or calls a provider.
# Provider Runtime Context Audit

- Provider runtime metadata must be propagated from the runtime contract SSOT at the callsite.
- `runtime_contract_active=false` is distinct from missing metadata; missing values are `unknown`.
- Provider context reports include execution mode, session ID, scope/task, and context provenance.
- Live summaries compare provider events only inside the selected running PID/session window.
- Dry-read and terminated process logs cannot overwrite the live provider context result.
- Provider metadata mismatch is an observability blocker, separate from AI action and order safety.
## LOCAL-First Provider Completion Summary

`local-first-gpt-cost-guard-v1-summary` is an observe-only Sprint checklist. It combines target PID/session runtime evidence with source-contract checks for LOCAL-first inference, escalation, provider cost guards, final provider routing, comparison training, and Korean reason visibility. It does not invoke providers or trading controls. External calls remain subject to cooldown, duplicate payload, hourly, daily, order-related, and estimated-cost limits.

## LOCAL Provider Outcome Learning Summary

`local-provider-outcome-learning-v1-summary --observe-only` checks decision registration, 5-minute/15-minute/1-hour scheduling, factual checkpoint evaluation, provider comparison, retrospective action classifiers, opportunity-cost evidence, dataset writers, and Korean outcome visibility. Runtime counts are scoped to the selected application PID/session. A zero evaluated count is valid before the first checkpoint is due; structural readiness and runtime activity are reported separately.

## LOCAL Training Dataset Curation Summary

`local-training-dataset-curation-v1-summary --observe-only` validates the curated schema, strict training gate, standardized exclusions, action/provider/opportunity tags, deduplicating writers, quality summary, and safe Korean status contract. It reports actual curated/excluded file presence and counts while treating a valid zero-record source as empty rather than failed. The mode reads existing runtime data and never invokes a provider or trading control.
# LOCAL Training Feature Pipeline v1

`local-training-feature-pipeline-v1-summary --observe-only` audits the model-neutral feature schema, all feature groups, retrospective labels, feature quality gate, atomic dataset outputs, time-based split readiness, and compatibility with the preceding LOCAL data Sprints. It reads only curated runtime records and never trains a model or invokes live inference. Missing factual source values remain null and are reflected in quality or exclusion results.
# LOCAL Model Training v1

`local-model-training-v1-summary --observe-only` verifies the real feature loader, stable matrix and label builders, baseline trainer, metrics status, model registry, artifact safety flags, no-data handling, and shadow-only prediction interface. A zero-row dataset passes as `no_data_training_ready` only when no model artifact was fabricated and the registry keeps live decision use disabled.
# LOCAL Model Live Integration v1

`--mode local-model-live-integration-v1-summary --observe-only` validates the trained-model registry, prediction feature contract, LOCAL_MODEL provider candidate policy, registry-gated live eligibility, observation fields, and the absence of direct order-layer dependencies. An honest `trained=false` registry is a valid no-model fallback: prediction remains unavailable and the existing LOCAL/external route stays active.
# LOCAL Model Live Outcome Calibration v1

`--mode local-model-live-outcome-calibration-v1-summary --observe-only` checks observed outcome loading, LOCAL_MODEL prediction matching, confidence buckets, action/task and risk calibration, recommendation-only routing metadata, calibration profile files, and prior Sprint compatibility. Zero usable records are reported as `no_data_calibration_ready`; the summary requires a null recommended threshold and `safe_for_live_expansion=false` in that state.
# Low-resource runtime stability summary

`--mode low-resource-runtime-stability-v1-summary --observe-only` audits the stability-first runtime profile without starting AITS or touching trading controls. It checks ON startup staging, chart and table repaint throttles, batched LIVE LOG updates, AI/indicator backpressure, resource health logging, safe UI-first degradation, and prohibited trading-layer diffs.

The summary is structural. A later user-operated ON session supplies runtime timing evidence; lack of such a session does not cause the structural safety audit to fabricate activity.
