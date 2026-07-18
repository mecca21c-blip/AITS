from __future__ import annotations

from typing import Any, Iterable, Mapping


EXPECTED_PROTECTIVE_RECOVERY = "expected_protective_recovery"
STATE_LOSS_RECOVERY = "managed_pool_state_loss_recovery"
NO_RECOVERY = "no_recovery"
UNSAFE_RECOVERY = "unsupported_recovery"


def classify_managed_pool_recovery(
    *,
    holding_rows: Iterable[Mapping[str, Any]],
    added_symbols: Iterable[str],
    dust_excluded_symbols: Iterable[str] = (),
    missing_symbols: Iterable[str] = (),
    non_holding_promotion: bool = False,
    persisted_symbols_expected: Iterable[str] = (),
) -> dict[str, Any]:
    """Classify recovery provenance without changing Managed Pool behavior."""
    holdings = {
        str(row.get("symbol") or row.get("market") or "").strip().upper(): dict(row)
        for row in holding_rows
        if isinstance(row, Mapping) and str(row.get("symbol") or row.get("market") or "").strip()
    }
    added = {str(value or "").strip().upper() for value in added_symbols if str(value or "").strip()}
    dust = {str(value or "").strip().upper() for value in dust_excluded_symbols if str(value or "").strip()}
    missing = {str(value or "").strip().upper() for value in missing_symbols if str(value or "").strip()}
    persisted = {str(value or "").strip().upper() for value in persisted_symbols_expected if str(value or "").strip()}
    manageable = {
        symbol for symbol, row in holdings.items()
        if bool(row.get("manageable_holding", True))
        and not bool(row.get("dust_holding") or row.get("is_dust_holding"))
        and float(row.get("qty") or row.get("quantity") or 0.0) > 0.0
    }
    unexpected = added - manageable
    if not added:
        classification = NO_RECOVERY
    elif non_holding_promotion or unexpected or bool(added & dust) or missing:
        classification = UNSAFE_RECOVERY
    elif persisted and added.issubset(persisted):
        classification = STATE_LOSS_RECOVERY
    else:
        classification = EXPECTED_PROTECTIVE_RECOVERY
    return {
        "classification": classification,
        "expected_protective_recovery": classification == EXPECTED_PROTECTIVE_RECOVERY,
        "state_loss_detected": classification == STATE_LOSS_RECOVERY,
        "safe_recovery": classification in {EXPECTED_PROTECTIVE_RECOVERY, NO_RECOVERY},
        "added_symbols": sorted(added),
        "manageable_holding_symbols": sorted(manageable),
        "unexpected_symbols": sorted(unexpected),
        "dust_recovery_detected": bool(added & dust),
        "non_holding_promotion_detected": bool(non_holding_promotion),
        "missing_symbols": sorted(missing),
    }
