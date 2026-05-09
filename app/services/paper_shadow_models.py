from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PaperShadowPosition:
    symbol: str
    provider: str
    entry_price: float
    current_price: float
    qty_virtual: float
    entry_time: str
    exit_time: str | None
    pnl_pct: float
    pnl_krw: float
    state: str
    scenario: str
    eta_minutes: int
    closed: bool
    metadata: dict = field(default_factory=dict)


@dataclass
class PaperShadowResult:
    symbol: str
    provider: str
    action: str
    applied: bool
    virtual_only: bool
    position: PaperShadowPosition | None
    reason: str
    error: str | None
    metadata: dict = field(default_factory=dict)


def _safety_metadata(extra: dict | None = None) -> dict:
    metadata = dict(extra or {})
    metadata["real_order"] = False
    metadata["submitted"] = 0
    return metadata


def build_sample_paper_shadow_position() -> PaperShadowPosition:
    return PaperShadowPosition(
        symbol="KRW-BTC",
        provider="mock",
        entry_price=100_000_000.0,
        current_price=100_000_000.0,
        qty_virtual=0.001,
        entry_time="sample",
        exit_time=None,
        pnl_pct=0.0,
        pnl_krw=0.0,
        state="watching",
        scenario="횡보 관찰형",
        eta_minutes=30,
        closed=False,
        metadata=_safety_metadata({"sample": True}),
    )


def build_sample_paper_shadow_result() -> PaperShadowResult:
    position = build_sample_paper_shadow_position()
    return PaperShadowResult(
        symbol=position.symbol,
        provider=position.provider,
        action="watch",
        applied=False,
        virtual_only=True,
        position=position,
        reason="sample_virtual_position_only",
        error=None,
        metadata=_safety_metadata({"sample": True}),
    )


__all__ = [
    "PaperShadowPosition",
    "PaperShadowResult",
    "build_sample_paper_shadow_position",
    "build_sample_paper_shadow_result",
]
