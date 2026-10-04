"""Margin waterfall, exact-sum bridge, and the RETAILER_RISK flag (PLAN.md
section 7). Every cost number is read via `registry.get()` — this is the
first module to actually consume the cost assumptions (A-013..A-017b)
that Phase 2/3 only reserved ids for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from backend.assumptions import registry
from backend.assumptions.assumptions import PACK_SIZE_L
from backend.engine.ids import QuantizedLever
from backend.engine.scenario import CostShock

ALUMINIUM_FORMATS = {"can_330ml", "multipack_6x330ml"}
PET_FORMATS = {"pet_500ml", "bottle_1500ml"}

_PACKAGING_ID_BY_FORMAT = {
    "can_330ml": "A-014a",
    "pet_500ml": "A-014b",
    "bottle_1500ml": "A-014c",
    "multipack_6x330ml": "A-014d",
}


def _cents(dollars: float) -> int:
    return int(Decimal(str(dollars)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cogs_per_unit(fmt: str, cost_shock: CostShock) -> float:
    """Raw material (sugar-shocked) + packaging (aluminium/PET-shocked) + variable mfg."""
    raw_material_per_l = registry.get("A-013").value * (1 + cost_shock.sugar_pct / 100.0)
    packaging_base = registry.get(_PACKAGING_ID_BY_FORMAT[fmt]).value
    packaging_shock_pct = (
        cost_shock.aluminium_pct
        if fmt in ALUMINIUM_FORMATS
        else cost_shock.pet_resin_pct
        if fmt in PET_FORMATS
        else 0.0
    )
    packaging = packaging_base * (1 + packaging_shock_pct / 100.0)
    variable_mfg_per_l = registry.get("A-015").value
    pack_size_l = PACK_SIZE_L[fmt]
    return raw_material_per_l * pack_size_l + packaging + variable_mfg_per_l * pack_size_l


def trade_spend(price: float, volume: float, lever: QuantizedLever) -> float:
    """Fixed listing/slotting terms plus promo-week funding (depth x weeks/4)."""
    fixed_trade_pct = registry.get("A-016").value
    gsv = price * volume
    promo_share = (lever.weeks_per_month / 4.0) * (lever.depth_pct / 100.0)
    return fixed_trade_pct * gsv + promo_share * gsv


def retailer_risk(price_index: float) -> bool:
    """Flags when the retailer's margin %, after partial pass-through of a
    manufacturer price move, falls below its hurdle. Without a pass-through
    rate below 1.0 both prices would move together 1:1 and this could never
    fire. `price_index` is the manufacturer's own invoice-price lever;
    baseline retailer markup is assumed calibrated so the baseline margin
    equals the hurdle exactly (margin == hurdle is not itself a risk — only
    erosion below it is), which is the simplest assumption that makes the
    flag both inert at baseline and reachable within the lever's bounds.
    """
    hurdle = registry.get("A-017").value
    pass_through = registry.get("A-017b").value
    # margin = 1 - mfg_price_1/shelf_price_1, with mfg/shelf prices normalised
    # relative to mfg_price_0=1 and shelf_price_0=1/(1-hurdle). Written this
    # way (instead of via a separately-rounded `1/(1-hurdle)` baseline shelf
    # price) margin == hurdle exactly in float at price_index=1.0, so
    # baseline never spuriously flags from rounding noise at the boundary.
    shelf_rel = 1.0 + (price_index - 1.0) * pass_through
    retailer_margin_pct = 1.0 - price_index * (1.0 - hurdle) / shelf_rel
    return retailer_margin_pct < hurdle


@dataclass
class Bridge:
    """Six components that sum exactly (in cents) to the total GP change.
    Any float rounding residual is forced onto whichever component is
    largest in magnitude, so `sum(components) == total` by construction.
    """

    price_cents: int
    volume_cents: int
    cross_pack_cents: int
    promo_cents: int
    trade_cents: int
    cogs_cents: int
    total_cents: int


def build_bridge(
    *,
    price_base: float,
    price_final: float,
    vol0: float,
    vol1: float,
    vol2: float,
    vol3: float,
    trade_base: float,
    trade_final: float,
    cogs_base: float,
    cogs_final: float,
) -> Bridge:
    """vol0..vol3 are the staged central-draw volumes: baseline, +own-price,
    +cross-pack, +promo (final). Each dollar component is an exact algebraic
    piece of GSV3-GSV0 (or the trade/COGS deltas), so summing them always
    equals GP_final - GP_base in full precision; only cent-rounding can make
    the parts disagree with independently-rounded endpoints, which the
    residual correction below removes.
    """
    components = {
        "price": (price_final - price_base) * vol0,
        "volume": price_final * (vol1 - vol0),
        "cross_pack": price_final * (vol2 - vol1),
        "promo": price_final * (vol3 - vol2),
        "trade": trade_base - trade_final,
        "cogs": cogs_base - cogs_final,
    }

    gp_base = price_base * vol0 - trade_base - cogs_base
    gp_final = price_final * vol3 - trade_final - cogs_final
    total_cents = _cents(gp_final) - _cents(gp_base)

    cents = {k: _cents(v) for k, v in components.items()}
    residual = total_cents - sum(cents.values())
    if residual:
        target = max(components, key=lambda k: abs(components[k]))
        cents[target] += residual

    return Bridge(
        price_cents=cents["price"],
        volume_cents=cents["volume"],
        cross_pack_cents=cents["cross_pack"],
        promo_cents=cents["promo"],
        trade_cents=cents["trade"],
        cogs_cents=cents["cogs"],
        total_cents=total_cents,
    )
