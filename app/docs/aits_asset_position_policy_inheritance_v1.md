# AITS Asset Position Policy Inheritance v1

## Goal

`AITS-ASSET-POSITION-POLICY-INHERITANCE-ROOT-FIX-01` defines the read-only
position-size policy inheritance contract. It does not force ON, raise caps,
fake balances, emit order intent, or submit orders.

## Owners

- Global position percent: `settings.strategy.pos_size_pct`
- Global default: `StrategyConfig.pos_size_pct = 2.5`
- Asset policy preview: `settings.ui_state.asset_policy_snapshots[*].max_weight_pct`
- Asset policy UI owner: `app/ui/app_gui.py` asset policy drawer
- ON preflight owner: `app/ui/app_gui.py::_preflight_check`

The asset policy drawer is currently preview/storage UI. Its saved snapshots
carry `preview_only=true` and `applied_to_order=false`.

## Inheritance Contract

```text
if asset_pos_size_pct > 0:
    effective_pos_size_pct = asset_pos_size_pct
    source = asset_override
else:
    effective_pos_size_pct = global_pos_size_pct
    source = global_inherited
```

`asset_pos_size_pct=0`, missing, or `None` means global inheritance. It is not a
zero position limit. Negative asset percentages are invalid and must be blocked
or rejected by validation.

## Preflight Stage Split

- ON start preflight is symbol-less. It uses `settings.strategy.pos_size_pct`.
- Candidate/order preflight may use a candidate symbol. At that stage, a
  positive asset override may replace the global percent.
- If a candidate asset value is `0%`, that candidate inherits the global
  percent.

## Current 2.5 Percent Source

The observed `pos_limit_krw=2830` with `available_krw=113201` comes from the
current global setting:

```text
113201 * 2.5 / 100 = 2830
```

That `2.5%` is the active `settings.strategy.pos_size_pct` value, not a direct
application of an asset-level `0%`.

## User Setting Guidance

For a 10000 KRW test with `available_krw=113201`, the minimum global position
percent is about `8.84%`. A practical setting is `10%`.

An asset override can also pass the position cap, for example:

```text
global=2.5%, asset=15%, available=113201
pos_limit_krw = 16980
effective cap = min(113201, 16980, 12000, 20000) = 12000
```

## Harness Modes

```powershell
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode asset-position-policy-inheritance-summary --observe-only
python tools/runtime_smoke/aits_qt_smoke_harness.py --mode live-on-preflight-position-policy-source-summary --observe-only
```

Both modes keep `actual_order=false`, `submitted_count=0`, and
`provider_external_call_count=0`.
