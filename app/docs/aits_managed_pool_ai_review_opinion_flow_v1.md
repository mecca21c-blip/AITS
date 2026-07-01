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
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode managed-pool-gpt-one-shot-opinion-proof --provider gpt --target-symbol KRW-BTC --allow-provider-calls --max-provider-calls 1 --timeout-sec 120
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
