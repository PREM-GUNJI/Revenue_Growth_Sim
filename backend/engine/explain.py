"""Read-only explanations derived from a scenario and its engine result.

Nothing here computes a new commercial number: `focal_bridge` adds up per-SKU bridge components the
engine already produced (integers, so the sum is exact), and `assumption_ids_for` lists which registry
assumptions a scenario's result depends on, decided by what the scenario changes.
"""

from __future__ import annotations

from backend.assumptions.assumptions import (
    FOCAL_BRAND,
    OWN_ELASTICITY_BY_FORMAT,
    PACKAGING_COST_PER_UNIT,
    PROMO_MECHANIC_MULTIPLIER,
    SKUS,
)
from backend.engine.batch import ScenarioResult
from backend.engine.scenario import Lever, Scenario

_SKU_FORMAT = {s["sku_id"]: s["format"] for s in SKUS}
_SKU_BRAND = {s["sku_id"]: s["brand"] for s in SKUS}
_FOCAL_SKUS = [sku for sku, brand in _SKU_BRAND.items() if brand == FOCAL_BRAND]
BRIDGE_COMPONENTS = ("price_cents", "volume_cents", "cross_pack_cents", "promo_cents", "trade_cents", "cogs_cents", "total_cents")

# Always part of a result: unit costs and the trade rate feed gross profit, the support check decides
# whether a number may be shown at all, and the four declared limitations hold for every scenario.
_ALWAYS = (
    "A-013", "A-015", "A-016", "A-022", "A-023", "A-018", "A-019", "A-020", "A-021",
    *(a.id for a in PACKAGING_COST_PER_UNIT.values()),
)


def assumption_ids_for(scenario: Scenario) -> list[str]:
    """Registry assumptions this scenario's result depends on, sorted.

    A price move brings in the own-price elasticity of each moved format, both cross elasticities and
    the retailer-risk settings; a promotion brings in the promo curve, pull-forward and the multiplier
    of each mechanic used. Costs, trade terms, the support check and the declared limitations always apply.
    """
    ids = set(_ALWAYS)
    moved_formats = set()
    mechanics = set()
    for sku, lever in scenario.levers.items():
        if sku not in _SKU_FORMAT:
            continue
        if lever.price_index != Lever().price_index:
            moved_formats.add(_SKU_FORMAT[sku])
        if lever.promo_depth_pct > 0:
            mechanics.add(lever.mechanic)
    if moved_formats:
        ids.update(OWN_ELASTICITY_BY_FORMAT[fmt].id for fmt in moved_formats)
        ids.update(("A-005", "A-006", "A-017", "A-017b"))
    if mechanics:
        ids.update(("A-007", "A-008", "A-012"))
        ids.update(PROMO_MECHANIC_MULTIPLIER[m].id for m in mechanics if m in PROMO_MECHANIC_MULTIPLIER)
    return sorted(ids)


def focal_bridge(result: ScenarioResult, *, major_units: bool = False) -> dict[str, float] | None:
    """The focal brand's gross-profit bridge: per-SKU components summed.

    Integers in minor currency units (hundredths of a rupee) by default, so the parts add up exactly to
    the total; with `major_units` the same figures in rupees, named without the `_cents` suffix, which is
    what a person or the agent should quote. None for a refused scenario, which has no numbers.
    """
    if result.status == "REFUSED" or not result.bridge:
        return None
    minor = {name: sum(getattr(result.bridge[sku], name) for sku in _FOCAL_SKUS) for name in BRIDGE_COMPONENTS}
    if not major_units:
        return minor
    return {name.removesuffix("_cents"): value / 100 for name, value in minor.items()}
