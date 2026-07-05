# AITS Asset Position Policy AI Dynamic v1

## Goal

`AITS-ASSET-POSITION-POLICY-AI-DYNAMIC-NO-GLOBAL-UI-FIX-01` corrects the
position policy contract. A missing or `0%` asset weight is not global
inheritance. It means AI dynamic position policy.

This document does not authorize orders, bypass RiskGuard, bypass
LivePreflight, fake balance, or submit anything.

## Owners

- Asset policy preview: `settings.ui_state.asset_policy_snapshots[*].max_weight_pct`
- Asset policy UI owner: `app/ui/app_gui.py` asset policy drawer
- ON preflight owner: `app/ui/app_gui.py::_preflight_check`
- Legacy global field: `settings.strategy.pos_size_pct`

`settings.strategy.pos_size_pct` may remain for backward compatibility, but it
is not exposed as a global UI control and is not used as the ON-start live
preflight blocker.

## Policy Contract

```text
if asset_max_weight_pct > 0:
    asset_policy_mode = asset_override
    user_pos_limit_applied = true
else:
    asset_policy_mode = ai_dynamic
    user_pos_limit_applied = false
```

`asset_max_weight_pct=0`, missing, or `None` means the user did not define a
manual per-asset cap. AITS leaves the asset allocation decision to AI dynamic
policy, then keeps the existing hard safety gates:

- configured order amount
- available KRW
- per-order hard cap
- guarded-window cap
- duplicate/relock
- RiskGuard
- LivePreflight
- one-shot unlock

Negative asset percentages are invalid and must block.

## Preflight Stage Split

- ON-start preflight is symbol-less. It cannot apply a candidate-specific asset
  override. It validates available KRW, configured order amount, per-order hard
  cap, guarded-window cap, provider readiness, and account readiness.
- Candidate/order preflight runs after `candidate_symbol` is known. A positive
  asset override can apply there. If the asset value is `0%` or missing, the
  candidate remains in AI dynamic mode.

## Current Example

With:

```text
available_krw = 113201
order_amount_krw = 10000
per_order_hard_cap_krw = 12000
total_guarded_window_cap_krw = 20000
```

ON-start effective cap is:

```text
min(113201, 12000, 20000) = 12000
```

That passes the 10000 KRW cap condition. The old `pos_size_pct=2.5%` value no
longer reduces ON-start effective cap to 2830 KRW.

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode asset-position-policy-inheritance-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode asset-position-policy-ai-dynamic-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-position-policy-source-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-ai-dynamic-cap-summary --observe-only
```

All modes keep `actual_order=false`, `submitted_count=0`, and
`provider_external_call_count=0`.
