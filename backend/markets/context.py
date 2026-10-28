"""Active market for the current request/evaluation (contextvars)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Iterator

from backend.assumptions.assumptions import ASSUMPTIONS, Assumption

DEFAULT_MARKET_ID = "in"


@dataclass(frozen=True)
class MarketCurrency:
    code: str
    symbol: str
    locale: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "symbol": self.symbol, "locale": self.locale}


@dataclass(frozen=True)
class Market:
    id: str
    label: str
    currency: MarketCurrency
    money: dict[str, float]
    demand: dict[str, float]
    generator: dict

    def overlay_ids(self) -> frozenset[str]:
        return frozenset(self.money) | frozenset(self.demand)

    def as_public(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "currency": self.currency.as_dict(),
        }


_active_market: ContextVar[Market | None] = ContextVar("active_market", default=None)


def get_active_market() -> Market | None:
    return _active_market.get()


def get_active_market_id() -> str:
    market = _active_market.get()
    return market.id if market is not None else DEFAULT_MARKET_ID


def clear_market() -> None:
    _active_market.set(None)


def bind_market(market: Market | None):
    """Set the active market and return a ContextVar token (for FastAPI async deps)."""
    return _active_market.set(market)


def unbind_market(token) -> None:
    try:
        _active_market.reset(token)
    except ValueError:
        _active_market.set(None)


@contextmanager
def use_market(market: Market | None) -> Iterator[Market | None]:
    """Install a market for the duration of the block (None = base India registry)."""
    token = _active_market.set(market)
    try:
        yield market
    finally:
        # FastAPI may enter a sync context manager in a worker thread; resetting a
        # token created in another Context raises ValueError — fall back to clear.
        try:
            _active_market.reset(token)
        except ValueError:
            _active_market.set(None)


def _rewrite_unit(unit: str | None, code: str) -> str | None:
    if unit is None:
        return None
    if unit == "INR" or unit.startswith("INR/"):
        return unit.replace("INR", code, 1)
    return unit


def _rewrite_label(label: str, code: str) -> str:
    return label.replace("(INR)", f"({code})").replace("INR", code)


def _scaled_range(
    base: Assumption, new_value: float
) -> tuple[float, float] | None:
    if base.valid_range is None or not isinstance(base.value, (int, float)) or base.value == 0:
        return base.valid_range
    lo, hi = base.valid_range
    ratio = float(new_value) / float(base.value)
    return (lo * ratio, hi * ratio)


def overlay_assumption(base: Assumption) -> Assumption:
    """Return the market-overlaid assumption, or the base when no overlay applies."""
    market = _active_market.get()
    if market is None or market.id == DEFAULT_MARKET_ID:
        return base
    value = market.money.get(base.id)
    from_demand = False
    if value is None:
        value = market.demand.get(base.id)
        from_demand = value is not None
    if value is None:
        return base
    valid_range = base.valid_range if from_demand else _scaled_range(base, value)
    if from_demand and base.valid_range is not None:
        lo, hi = base.valid_range
        # Keep the central value inside the drawable range used by ParamDraws.
        if not (lo <= value <= hi):
            pad = abs(value) * 0.05
            valid_range = (min(lo, value) - pad, max(hi, value) + pad)
    return replace(
        base,
        value=value,
        unit=_rewrite_unit(base.unit, market.currency.code),
        label=_rewrite_label(base.label, market.currency.code),
        valid_range=valid_range,
        rationale=(
            f"{base.rationale} Overlaid for the {market.label} market pack "
            f"({market.currency.code}); synthetic, not a live FX conversion."
        ),
        reference=(
            f"Market pack `{market.id}` synthetic overlay. "
            f"{base.reference or ''}".strip()
        ),
    )


def resolve_assumption(assumption_id: str) -> Assumption:
    """Look up an assumption applying the active market overlay."""
    return overlay_assumption(ASSUMPTIONS[assumption_id])
