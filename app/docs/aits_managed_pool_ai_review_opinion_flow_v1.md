# AITS Managed Pool AI Review Opinion Flow v1

Purpose: document the observe-only Managed Pool AI review queue and LOCAL
opinion proof path.

## Owners

- Queue owner: `MainWindow._build_managed_pool_ai_review_queue`
- Freshness owner: `MainWindow._build_managed_pool_ai_review_sla_state`
- Row tooltip owner: `MainWindow._build_ai_managed_row_tooltip`
- Table owner: `tbl_ai_managed`

The queue is built from `managed_pool_rows`/`ai_managed_rows`, row scores,
freshness metadata, holding priority, and manual hold state. It is a review
surface only and does not submit orders.

## Trigger Policy

Managed rows can enter review when analysis is missing or stale, score changes,
market data is stale, or holding-specific conditions require attention. The UI
copy `AI 재분석은 수동 실행 필요` means GPT/Gemini reanalysis is not automatic.

Default proof policy:

- LOCAL/calculation opinion payloads are allowed.
- GPT/Gemini external calls are blocked unless a separate provider-call Goal
  explicitly allows them.
- Provider one-shot proof requires `--allow-provider-calls` and a call budget of
  `--max-provider-calls 1`.
- DecisionRouter final action is unchanged.
- `order_execution=false`.

## UI Overlay Policy

`managed_pool_ai_opinion_v1` can be applied to the Managed Pool table as a
display-only overlay. The overlay is keyed by symbol in
`MainWindow._aits_last_managed_pool_ai_opinion_overlay` and is merged at render
time by `MainWindow._populate_ai_managed_table_cells` and
`MainWindow._build_ai_managed_row_tooltip`.

The overlay may replace the visible status label with the opinion
`status_label` and append provider, confidence, reason, next action, freshness,
request id, and safety text to the tooltip. It must not persist changes to
`managed_pool_rows`, must not change protection/holding/source fields, and must
always keep `order_execution=false` and `final_action_unchanged=true`.

Tooltip readability is handled by the global `QToolTip` stylesheet. The content
contract is unchanged: AI opinion, holding, rotation, and protection reasons are
still merged into the same hover text, only rendered with a light card style.
Managed Pool row tooltips also wrap that same content in an escaped HTML light
card so OS/native tooltip dark backgrounds do not hide the text.

## Opinion Schema

`managed_pool_ai_opinion_v1` fields:

- `symbol`
- `provider`
- `provider_external_call=false`
- `source=local_calculation`
- `ai_score`
- `opinion`
- `status_label`
- `confidence`
- `reason`
- `next_action`
- `freshness`
- `order_execution=false`
- `final_action_unchanged=true`

User-facing statuses include `관망`, `매수대기`, `교체검토`, `매도검토`,
`데이터부족`, and `재분석필요`. In the default proof, generated opinions are
LOCAL reference opinions, not order signals.

## Proof Commands

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-review-queue-proof --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-flow-proof --observe-only --provider local
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-ai-opinion-ui-apply-proof --observe-only --provider local --target-symbol KRW-BTC
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-ui-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
```

PASS requires queue/opinion payloads to be present, provider external call count
to remain `0`, Managed Pool mutation to remain false, and order-risk markers to
remain false.

For the GPT/Gemini one-shot proof, PASS additionally requires provider call
count to be `<= 1`, response confirmation, normalized
`managed_pool_ai_opinion_v1`, `order_execution=false`,
`final_action_unchanged=true`, and Managed Pool mutation false. If the provider
key is missing or readiness is false, the proof reports partial/NO-GO without
calling the provider.

The UI overlay proofs additionally require `overlay_created=true`, a visible
status sample, a tooltip sample, Managed Pool mutation false, and provider call
count `0` for LOCAL or `<= 1` for GPT/Gemini one-shot proof.

## Manual AI Refresh Row Freshness Link

Manual `AI 분석 새로고침` results are linked to the matching Managed Pool row through a display-only `managed_pool_ai_opinion_v1` overlay. When the refresh result symbol matches a Managed Pool row, the row freshness state can be treated as fresh with the label `최신 · 수동 AI 분석 반영`; the row tooltip then shows provider, opinion, reason, next action, request id, and the safety note that no order or final action changed.

This overlay does not persist or mutate `managed_pool_rows`; it is UI/freshness state only. If the refresh result has no target symbol or the symbol is not in the Managed Pool, the existing stale/manual-required copy remains.

## Korean Tooltip Labels

Managed Pool AI opinion tooltips keep the `managed_pool_ai_opinion_v1` payload
unchanged, but render user-facing labels in Korean. Provider, reason, freshness,
and request metadata are displayed as `분석 엔진`, `판단 근거`, `분석 상태`, and
`요청 ID`. Freshness/source code values are humanized for display only, for
example `fresh_manual_refresh` is shown as `최신 · 수동 AI 분석 반영`.

This is UI copy only. It does not change freshness logic, provider policy,
DecisionRouter final action, order execution, or Managed Pool persistence.

## GPT Opinion Payload Quality

Managed Pool GPT/Gemini one-shot opinion proof uses a dedicated
`managed_pool_ai_opinion_request_v1` compact payload instead of relying on the
Router verification payload shape. The request is for display/review opinion
generation only and includes symbol, display name, AITS score, current status,
candidate/row reason, managed source, recent movement fields, and explicit
safety constraints (`order_execution=false`, `actual_order=false`,
`final_action_unchanged=true`, `managed_pool_mutation=false`).

The provider result is normalized into `managed_pool_ai_opinion_v1`. The
normalizer accepts only display statuses such as `관망`, `매수대기`, `교체검토`,
`매도검토`, and `데이터부족`, and it replaces execution-block-only rationale
with user-facing managed-pool rationale. This changes tooltip/report quality
only; it does not route or execute orders.

## Manual Refresh Dedicated Opinion Payload

When the user runs manual `AI 분석 새로고침` for a symbol that belongs to the Managed Pool, the refresh path uses the dedicated `managed_pool_ai_opinion_request_v1` payload instead of the Router verification adapter. The request remains a suggestion-only Managed Pool opinion request: `order_execution=false`, `actual_order=false`, `final_action_unchanged=true`, and `managed_pool_mutation=false`.

The result is normalized into `managed_pool_ai_opinion_v1`, then applied to the display-only row opinion/freshness overlay. The overlay may update status and tooltip copy, but it does not persist row changes. Provider calls remain behind an explicit proof flag and a one-call budget. Execution-block-only or stale manual-required rationale is not used as the primary user-facing reason.

### Fresh Opinion Reason Consistency

Fresh Managed Pool AI opinion overlays must keep freshness and explanation copy
consistent. When `freshness` starts with `fresh_`, or the source is
`manual_ai_refresh`, `gpt_one_shot_opinion`, or `local_calculation` with a
confirmed response, stale/manual-required fallback phrases are not shown as the
main `reason` or `next_action`.

Examples of stale phrases guarded in fresh overlays include manual refresh
required, analysis required, no current AI analysis, until AI analysis
completes, and Korean equivalents such as "AI 재분석은 수동 실행 필요" and
"수동 AI 재분석". For fresh `data_insufficient` opinions, the display fallback
is conservative observation copy: current data is insufficient, re-evaluate
after more data, and no order is executed.

This is display normalization only. It does not change the provider payload
schema, freshness decision ownership, Managed Pool persistence, DecisionRouter
final action, or any execution path.

## Manual Refresh Target Symbol E2E

Manual Managed Pool AI refresh must preserve the selected row symbol through the
entire display-only opinion path. For a managed-tab refresh, the selected
`tblAiManaged` row is resolved by
`MainWindow._current_managed_table_selection_for_ai_refresh` and
`MainWindow._resolve_ai_refresh_target_symbol`; if no valid row is selected, the
refresh is skipped instead of falling back to BTC or another symbol.

The E2E proof verifies that `selected_symbol`, the
`managed_pool_ai_opinion_request_v1` payload symbol, and the row overlay symbol
are identical. It also verifies `fallback_used=false`,
`overlay_applied_to_target_only=true`, no Managed Pool persistence mutation, no
order execution, and no DecisionRouter final-action change. LOCAL proof keeps
provider calls at `0`; GPT/Gemini remains available only behind an explicit
one-call proof flag.
