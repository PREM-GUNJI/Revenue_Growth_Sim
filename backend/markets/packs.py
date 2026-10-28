"""Load market packs from YAML under backend/markets/packs/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.markets.context import Market, MarketCurrency

_PACKS_DIR = Path(__file__).resolve().parent / "packs"
MONEY_IDS = frozenset({
    "A-013", "A-014a", "A-014b", "A-014c", "A-014d", "A-015",
    "A-028", "A-029", "A-030", "A-031", "A-035",
})
DEMAND_IDS = frozenset({
    "A-001", "A-002", "A-003", "A-004", "A-005", "A-006",
    "A-007", "A-008", "A-009", "A-010", "A-011", "A-012",
})


def _parse(raw: dict[str, Any], path: Path) -> Market:
    try:
        currency_raw = raw["currency"]
        market = Market(
            id=str(raw["id"]),
            label=str(raw["label"]),
            currency=MarketCurrency(
                code=str(currency_raw["code"]),
                symbol=str(currency_raw["symbol"]),
                locale=str(currency_raw["locale"]),
            ),
            money={str(k): float(v) for k, v in (raw.get("money") or {}).items()},
            demand={str(k): float(v) for k, v in (raw.get("demand") or {}).items()},
            generator=dict(raw.get("generator") or {}),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid market pack {path}: {error}") from error
    unknown_money = set(market.money) - MONEY_IDS
    unknown_demand = set(market.demand) - DEMAND_IDS
    if unknown_money:
        raise ValueError(f"{path}: unknown money ids {sorted(unknown_money)}")
    if unknown_demand:
        raise ValueError(f"{path}: unknown demand ids {sorted(unknown_demand)}")
    if market.id != path.stem:
        raise ValueError(f"{path}: id {market.id!r} does not match filename stem")
    return market


@lru_cache(maxsize=1)
def _all_markets() -> dict[str, Market]:
    markets: dict[str, Market] = {}
    for path in sorted(_PACKS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"market pack {path} must be a mapping")
        market = _parse(raw, path)
        markets[market.id] = market
    if "in" not in markets:
        raise ValueError("market pack 'in' (India) is required")
    return markets


def list_markets() -> list[Market]:
    """All registered markets, India first, then the rest by id."""
    markets = _all_markets()
    rest = sorted((m for mid, m in markets.items() if mid != "in"), key=lambda m: m.id)
    return [markets["in"], *rest]


def load_market(market_id: str) -> Market:
    markets = _all_markets()
    try:
        return markets[market_id]
    except KeyError as error:
        known = ", ".join(sorted(markets))
        raise KeyError(f"unknown market {market_id!r}; known: {known}") from error
