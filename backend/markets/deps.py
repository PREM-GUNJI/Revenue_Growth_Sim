"""FastAPI helpers to install the active market for a request."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, Query

from backend.markets.context import DEFAULT_MARKET_ID, Market, bind_market, unbind_market, use_market
from backend.markets.packs import list_markets, load_market


def resolve_market_id(market_id: str | None) -> str:
    mid = (market_id or DEFAULT_MARKET_ID).strip().lower()
    try:
        load_market(mid)
    except KeyError as error:
        known = ", ".join(m.id for m in list_markets())
        raise HTTPException(status_code=422, detail=f"Unknown market {mid!r}. Known: {known}") from error
    return mid


@contextmanager
def market_scope(market_id: str | None) -> Iterator[Market]:
    market = load_market(resolve_market_id(market_id))
    with use_market(market):
        yield market


async def market_from_query(
    market: Annotated[str | None, Query(description="Market pack id (in, us, eu)")] = None,
) -> AsyncIterator[Market]:
    """Install the market on the async request context (avoids ContextVar/thread-pool reset errors)."""
    active = load_market(resolve_market_id(market))
    token = bind_market(active)
    try:
        yield active
    finally:
        unbind_market(token)


ActiveMarket = Annotated[Market, Depends(market_from_query)]
