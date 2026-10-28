"""Multi-market packs: currency, money and demand overlays for synthetic markets.

India (`in`) is the base registry. Other markets overlay documented synthetic
values; they are not live FX conversions of one dataset.
"""

from __future__ import annotations

from backend.markets.context import (
    DEFAULT_MARKET_ID,
    Market,
    MarketCurrency,
    clear_market,
    get_active_market,
    get_active_market_id,
    use_market,
)
from backend.markets.packs import list_markets, load_market

__all__ = [
    "DEFAULT_MARKET_ID",
    "Market",
    "MarketCurrency",
    "clear_market",
    "get_active_market",
    "get_active_market_id",
    "list_markets",
    "load_market",
    "use_market",
]
