"""Single structured spec for every engine/generator parameter (PLAN.md section 5).

Nothing here is fitted or learned. Every `Assumption` has a value, a
plausible range, a source and a rationale. Phase 3 adds `registry.py`,
a read-tracking access layer over `ASSUMPTIONS` below — this module only
defines the values; it has no I/O and no randomness of its own.

Two kinds of constants live here:
- `ASSUMPTIONS`: parameters the *engine* reads via the registry (Phase 3).
- `GENERATOR_SEED`: generator-only inputs (e.g. seed baseline volumes,
  seasonality, noise scale, list prices) that shape the synthetic history
  but are never read by the engine, so they carry no Assumption id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

Source = Literal["data-derived", "business-input", "modelling-choice"]


@dataclass(frozen=True)
class Assumption:
    id: str
    label: str
    value: object
    unit: str | None
    source: Source
    rationale: str
    valid_range: tuple[float, float] | None = None


# --- Portfolio catalog -------------------------------------------------
# 5 fictional brands x 4 pack formats = 20 SKUs (PLAN.md section 3 started with 3 brands / 12 SKUs).
BRANDS = ["Aurora", "Boreal", "Comet", "Delta", "Ember"]
FORMATS = ["can_330ml", "pet_500ml", "bottle_1500ml", "multipack_6x330ml"]
PACK_SIZE_L = {
    "can_330ml": 0.33,
    "pet_500ml": 0.50,
    "bottle_1500ml": 1.50,
    "multipack_6x330ml": 1.98,  # 6 x 330ml
}
REGIONS = ["North", "South", "West"]
STORES_PER_REGION = 8  # generator-only realism dimension; see GENERATOR_SEED note
N_WEEKS = 104
PROMO_MECHANICS = ["none", "TPR", "feature_display", "BOGO"]
PROMO_DEPTH_STEPS = [0, 5, 10, 15, 20, 25, 30]  # observed depths, in percent


def sku_id(brand: str, fmt: str) -> str:
    return f"{brand}-{fmt}"


SKUS: list[dict] = [
    {"sku_id": sku_id(b, f), "brand": b, "format": f, "pack_size_l": PACK_SIZE_L[f]}
    for b in BRANDS
    for f in FORMATS
]
SKU_IDS = [s["sku_id"] for s in SKUS]
N_SKUS = len(SKU_IDS)  # 20

# --- Own-price elasticity by format (larger packs less elastic) --------
OWN_ELASTICITY_BY_FORMAT: dict[str, Assumption] = {
    "can_330ml": Assumption(
        id="A-001",
        label="Own-price elasticity, 330ml can",
        value=-2.3,
        unit=None,
        source="modelling-choice",
        rationale=(
            "Smallest, most impulse-driven format; set near the elastic end of the "
            "brief's -0.8 to -2.5 CPG range."
        ),
        valid_range=(-2.5, -1.9),
    ),
    "pet_500ml": Assumption(
        id="A-002",
        label="Own-price elasticity, 500ml PET",
        value=-1.6,
        unit=None,
        source="modelling-choice",
        rationale="Mid-size single-serve format; mid-range elasticity.",
        valid_range=(-1.9, -1.3),
    ),
    "bottle_1500ml": Assumption(
        id="A-003",
        label="Own-price elasticity, 1.5L sharing bottle",
        value=-1.1,
        unit=None,
        source="modelling-choice",
        rationale="Larger take-home format; less elastic than single-serve.",
        valid_range=(-1.4, -0.9),
    ),
    "multipack_6x330ml": Assumption(
        id="A-004",
        label="Own-price elasticity, 6x330ml multipack",
        value=-0.9,
        unit=None,
        source="modelling-choice",
        rationale="Largest committed-purchase format; least elastic in the portfolio.",
        valid_range=(-1.1, -0.8),
    ),
}

# --- Cross-elasticity (within-brand stronger than across-brand) --------
CROSS_ELASTICITY_WITHIN_BRAND = Assumption(
    id="A-005",
    label="Cross-price elasticity, within-brand (different format)",
    value=0.18,
    unit=None,
    source="modelling-choice",
    rationale="Formats of the same brand substitute for each other more than across brands.",
    valid_range=(0.10, 0.30),
)
CROSS_ELASTICITY_ACROSS_BRAND = Assumption(
    id="A-006",
    label="Cross-price elasticity, across-brand",
    value=0.05,
    unit=None,
    source="modelling-choice",
    rationale="Weak substitution between competing brands; smaller than within-brand.",
    valid_range=(0.02, 0.10),
)

# --- Promo response ------------------------------------------------------
PROMO_SATURATION_K = Assumption(
    id="A-007",
    label="Promo depth saturation rate",
    value=6.0,
    unit=None,
    source="modelling-choice",
    rationale="Shapes f(depth)=1-exp(-k*depth); k=6 gives strong saturation by 30% depth.",
    valid_range=(4.0, 8.0),
)
PROMO_LIFT_SCALE = Assumption(
    id="A-008",
    label="Promo lift scale (b_promo)",
    value=0.9,
    unit=None,
    source="modelling-choice",
    rationale="Log-volume lift multiplier applied to the saturating depth curve.",
    valid_range=(0.6, 1.2),
)
PROMO_MECHANIC_MULTIPLIER: dict[str, Assumption] = {
    "TPR": Assumption(
        id="A-009",
        label="Promo mechanic multiplier, TPR (temporary price reduction)",
        value=1.0,
        unit=None,
        source="modelling-choice",
        rationale="Baseline mechanic; no extra lift beyond the depth curve.",
        valid_range=(1.0, 1.0),
    ),
    "feature_display": Assumption(
        id="A-010",
        label="Promo mechanic multiplier, feature & display",
        value=1.25,
        unit=None,
        source="modelling-choice",
        rationale="In-store visibility adds roughly 25% on top of the depth curve.",
        valid_range=(1.15, 1.35),
    ),
    "BOGO": Assumption(
        id="A-011",
        label="Promo mechanic multiplier, BOGO",
        value=1.4,
        unit=None,
        source="modelling-choice",
        rationale="BOGO drives the largest lift of the three modelled mechanics.",
        valid_range=(1.3, 1.5),
    ),
}
PULL_FORWARD_SHARE = Assumption(
    id="A-012",
    label="Post-promo pull-forward share",
    value=0.20,
    unit=None,
    source="modelling-choice",
    rationale="15-25% of a promo's incremental lift is pulled forward from the following week.",
    valid_range=(0.15, 0.25),
)

# --- Cost inputs (business inputs; used by the engine's margin waterfall) --
RAW_MATERIAL_COST_PER_L = Assumption(
    id="A-013",
    label="Raw material cost per litre",
    value=0.12,
    unit="$/L",
    source="business-input",
    rationale="Representative CPG raw-material cost (sweetener, water treatment, CO2).",
    valid_range=(0.08, 0.20),
)
PACKAGING_COST_PER_UNIT: dict[str, Assumption] = {
    "can_330ml": Assumption(
        id="A-014a",
        label="Packaging cost per unit, 330ml can",
        value=0.08,
        unit="$/unit",
        source="business-input",
        rationale="Aluminium can stock is the most expensive packaging per unit volume.",
        valid_range=(0.06, 0.12),
    ),
    "pet_500ml": Assumption(
        id="A-014b",
        label="Packaging cost per unit, 500ml PET",
        value=0.05,
        unit="$/unit",
        source="business-input",
        rationale="PET bottle, mid packaging cost.",
        valid_range=(0.03, 0.08),
    ),
    "bottle_1500ml": Assumption(
        id="A-014c",
        label="Packaging cost per unit, 1.5L bottle",
        value=0.12,
        unit="$/unit",
        source="business-input",
        rationale="Larger PET bottle, more resin per unit.",
        valid_range=(0.09, 0.16),
    ),
    "multipack_6x330ml": Assumption(
        id="A-014d",
        label="Packaging cost per unit, 6x330ml multipack",
        value=0.25,
        unit="$/unit",
        source="business-input",
        rationale="6 cans plus multipack wrap/carton.",
        valid_range=(0.20, 0.32),
    ),
}
VARIABLE_MANUFACTURING_COST_PER_L = Assumption(
    id="A-015",
    label="Variable manufacturing cost per litre",
    value=0.20,
    unit="$/L",
    source="business-input",
    rationale="Filling, labour and energy cost, flat across formats.",
    valid_range=(0.15, 0.28),
)
FIXED_TRADE_TERMS_PCT = Assumption(
    id="A-016",
    label="Fixed trade terms, percent of GSV",
    value=0.05,
    unit="pct of GSV",
    source="business-input",
    rationale="Standing listing/slotting fees independent of promo activity.",
    valid_range=(0.02, 0.08),
)
RETAILER_HURDLE_MARGIN_PCT = Assumption(
    id="A-017",
    label="Retailer hurdle margin",
    value=0.25,
    unit="pct of shelf price",
    source="business-input",
    rationale="Standard retailer minimum margin requirement for the RETAILER_RISK flag.",
    valid_range=(0.20, 0.30),
)
RETAILER_PRICE_PASS_THROUGH = Assumption(
    id="A-017b",
    label="Retailer price pass-through rate",
    value=0.6,
    unit=None,
    source="modelling-choice",
    rationale=(
        "Share of a manufacturer list-price change the retailer passes to shelf price. "
        "Without a pass-through rate below 1.0, retailer margin % never moves and "
        "RETAILER_RISK could never fire — this fixes that."
    ),
    valid_range=(0.3, 0.9),
)

# --- Declared "no X" modelling assumptions (qualitative) ----------------
NO_COMPETITOR_REACTION = Assumption(
    id="A-018",
    label="No competitor reaction",
    value="assumed",
    unit=None,
    source="modelling-choice",
    rationale="Out of scope for a parametric single-portfolio engine; stated in docs/HONESTY.md.",
)
NO_DISTRIBUTION_CHANGES = Assumption(
    id="A-019",
    label="No distribution changes",
    value="assumed",
    unit=None,
    source="modelling-choice",
    rationale="Store count and assortment are held fixed; only price/promo/pack-mix move.",
)
STATIONARY_SEASONALITY = Assumption(
    id="A-020",
    label="Stationary seasonality",
    value="assumed",
    unit=None,
    source="modelling-choice",
    rationale="The seasonal curve used by the generator repeats identically every year.",
)
PACK_CHANGES_OBSERVED_SIZES_ONLY = Assumption(
    id="A-021",
    label="Pack changes only among observed sizes",
    value="assumed",
    unit=None,
    source="data-derived",
    rationale="Only the 4 catalog formats exist in the data; any other size is REFUSED.",
)
JOINT_SUPPORT_MIN_ROWS = Assumption(
    id="A-022",
    label="Minimum local rows for joint support",
    value=1,
    unit="rows",
    source="modelling-choice",
    rationale="At least one observation in the price-bin neighbourhood is required; empty joint cells are refused.",
    valid_range=(1, 100),
)
JOINT_SUPPORT_COMFORT_ROWS = Assumption(
    id="A-023",
    label="Comfortable local support row count",
    value=10,
    unit="rows",
    source="modelling-choice",
    rationale="Sparse occupied neighbourhoods remain evaluable but are labelled EDGE below this count.",
    valid_range=(1, 1000),
)
SCENARIO_CHUNK_SIZE = Assumption(
    id="A-024",
    label="Scenario evaluation chunk size",
    value=4096,
    unit="scenarios",
    source="modelling-choice",
    rationale="Bounds temporary array memory while keeping each scenario chunk vectorised across draws and SKUs.",
    valid_range=(32, 8192),
)
SUPPORT_DECISION_CACHE_SIZE = Assumption(
    id="A-025",
    label="Support decision cache size",
    value=32768,
    unit="entries",
    source="modelling-choice",
    rationale="Bounds memory used to reuse deterministic support decisions for repeated scenario levers.",
    valid_range=(128, 131072),
)
SYNTHETIC_CONSUMER_SAMPLE = Assumption(
    id="A-026", label="Default synthetic consumer sample size", value=250,
    unit="respondents", source="modelling-choice",
    rationale="A fixed illustrative sample keeps consumer evidence reproducible and is not a claim about real research sample adequacy.",
    valid_range=(1, 10000),
)
CONJOINT_UTILITY_SCALE = Assumption(
    id="A-027", label="Conjoint supplied utility scale", value=1.0,
    unit="utility units", source="modelling-choice",
    rationale="Multinomial logit uses supplied synthetic utilities without fitting or estimating them.",
    valid_range=(0.01, 10.0),
)

# --- Synthetic consumer evidence + pricing research (supporting layer) --
# Consumer research only proposes candidate prices/configurations; every
# commercial number still comes from the deterministic engine.
REFERENCE_PRICE_BY_FORMAT: dict[str, Assumption] = {
    fmt: Assumption(
        id=aid, label=f"Reference shelf price, {label} (INR)", value=price, unit="INR",
        source="business-input",
        rationale="Current synthetic shelf price used to turn a researched price into the engine's price_index (candidate / reference).",
        valid_range=(rng_lo, rng_hi),
    )
    for fmt, aid, label, price, rng_lo, rng_hi in (
        ("can_330ml", "A-028", "330ml can", 40.0, 20.0, 80.0),
        ("pet_500ml", "A-029", "500ml PET", 45.0, 25.0, 90.0),
        ("bottle_1500ml", "A-030", "1.5L bottle", 75.0, 40.0, 150.0),
        ("multipack_6x330ml", "A-031", "6x330ml multipack", 120.0, 60.0, 240.0),
    )
}
WTP_CANDIDATE_QUANTILES = Assumption(
    id="A-032", label="Willingness-to-pay candidate percentiles", value=[0.25, 0.5, 0.75],
    unit="fraction", source="modelling-choice",
    rationale="Descriptive percentiles of synthetic respondent WTP offered as candidate prices; they are candidates, not forecasts.",
    valid_range=(0.0, 1.0),
)
GABOR_GRANGER_ACCEPTANCE_THRESHOLD = Assumption(
    id="A-033", label="Gabor-Granger acceptance threshold", value=0.5, unit="fraction",
    source="modelling-choice",
    rationale="Highest tested price still accepted by at least this share of respondents is offered as a candidate.",
    valid_range=(0.05, 0.95),
)
GABOR_GRANGER_PRICE_GRID = Assumption(
    id="A-034", label="Gabor-Granger default price grid (x reference price)",
    value=[0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2], unit="price index", source="modelling-choice",
    rationale="Default tested prices as multiples of the pack's reference price, spanning the engine's observed price range and a little beyond so edge refusals stay visible.",
    valid_range=(0.5, 2.0),
)
RESEARCH_PRICE_GRID_STEP = Assumption(
    id="A-035", label="Van Westendorp price grid step (INR)", value=0.5, unit="INR",
    source="modelling-choice",
    rationale="Resolution of the price grid on which cumulative curves are intersected; coarser grids move intersections by at most one step.",
    valid_range=(0.1, 5.0),
)
CONJOINT_HETEROGENEITY_WEIGHT = Assumption(
    id="A-036", label="Conjoint respondent heterogeneity weight", value=1.0, unit="weight",
    source="modelling-choice",
    rationale="Scales a respondent's price and promotion part-worths by 1 + weight x (sensitivity - 0.5), where 0.5 is the midpoint of the 0-1 sensitivity scale. Deterministic; nothing is fitted.",
    valid_range=(0.0, 2.0),
)
CONJOINT_SUPPLIED_PART_WORTHS = Assumption(
    id="A-037", label="Supplied synthetic conjoint part-worths",
    value={
        "brand": {"Aurora": 0.35, "Boreal": 0.0, "Comet": -0.25, "Delta": 0.15, "Ember": -0.4},
        "pack": {"can_330ml": 0.0, "pet_500ml": 0.2, "bottle_1500ml": 0.1, "multipack_6x330ml": 0.15},
        "pack_match_bonus": 0.5,
        "price_slope": -6.0,
        "promotion": {"None": 0.0, "10% off": 0.35, "20% off": 0.6},
    },
    unit="utility units", source="modelling-choice",
    rationale="Illustrative part-worths supplied by the analyst. They are inputs to a deterministic multinomial-logit simulation and are never estimated or fitted from data. price_slope is utility per +100% price versus the pack's reference price.",
    valid_range=(-10.0, 10.0),
)

ASSUMPTIONS: dict[str, Assumption] = {
    **{a.id: a for a in OWN_ELASTICITY_BY_FORMAT.values()},
    CROSS_ELASTICITY_WITHIN_BRAND.id: CROSS_ELASTICITY_WITHIN_BRAND,
    CROSS_ELASTICITY_ACROSS_BRAND.id: CROSS_ELASTICITY_ACROSS_BRAND,
    PROMO_SATURATION_K.id: PROMO_SATURATION_K,
    PROMO_LIFT_SCALE.id: PROMO_LIFT_SCALE,
    **{a.id: a for a in PROMO_MECHANIC_MULTIPLIER.values()},
    PULL_FORWARD_SHARE.id: PULL_FORWARD_SHARE,
    RAW_MATERIAL_COST_PER_L.id: RAW_MATERIAL_COST_PER_L,
    **{a.id: a for a in PACKAGING_COST_PER_UNIT.values()},
    VARIABLE_MANUFACTURING_COST_PER_L.id: VARIABLE_MANUFACTURING_COST_PER_L,
    FIXED_TRADE_TERMS_PCT.id: FIXED_TRADE_TERMS_PCT,
    RETAILER_HURDLE_MARGIN_PCT.id: RETAILER_HURDLE_MARGIN_PCT,
    RETAILER_PRICE_PASS_THROUGH.id: RETAILER_PRICE_PASS_THROUGH,
    NO_COMPETITOR_REACTION.id: NO_COMPETITOR_REACTION,
    NO_DISTRIBUTION_CHANGES.id: NO_DISTRIBUTION_CHANGES,
    STATIONARY_SEASONALITY.id: STATIONARY_SEASONALITY,
    PACK_CHANGES_OBSERVED_SIZES_ONLY.id: PACK_CHANGES_OBSERVED_SIZES_ONLY,
    JOINT_SUPPORT_MIN_ROWS.id: JOINT_SUPPORT_MIN_ROWS,
    JOINT_SUPPORT_COMFORT_ROWS.id: JOINT_SUPPORT_COMFORT_ROWS,
    SCENARIO_CHUNK_SIZE.id: SCENARIO_CHUNK_SIZE,
    SUPPORT_DECISION_CACHE_SIZE.id: SUPPORT_DECISION_CACHE_SIZE,
    SYNTHETIC_CONSUMER_SAMPLE.id: SYNTHETIC_CONSUMER_SAMPLE,
    CONJOINT_UTILITY_SCALE.id: CONJOINT_UTILITY_SCALE,
    **{a.id: a for a in REFERENCE_PRICE_BY_FORMAT.values()},
    WTP_CANDIDATE_QUANTILES.id: WTP_CANDIDATE_QUANTILES,
    GABOR_GRANGER_ACCEPTANCE_THRESHOLD.id: GABOR_GRANGER_ACCEPTANCE_THRESHOLD,
    GABOR_GRANGER_PRICE_GRID.id: GABOR_GRANGER_PRICE_GRID,
    RESEARCH_PRICE_GRID_STEP.id: RESEARCH_PRICE_GRID_STEP,
    CONJOINT_HETEROGENEITY_WEIGHT.id: CONJOINT_HETEROGENEITY_WEIGHT,
    CONJOINT_SUPPLIED_PART_WORTHS.id: CONJOINT_SUPPLIED_PART_WORTHS,
}

# Research-layer ids, so provenance can separate them from engine assumptions.
RESEARCH_ASSUMPTION_IDS = sorted(
    ["A-026", "A-027", "A-032", "A-033", "A-034", "A-035", "A-036", "A-037"]
    + [a.id for a in REFERENCE_PRICE_BY_FORMAT.values()]
)


def build_elasticity_matrix() -> np.ndarray:
    """(N_SKUS, N_SKUS) matrix: diagonal = own elasticity, off-diagonal = cross.

    Used by both the generator (Phase 1) and the engine/model (Phase 2/4) so
    the two can never drift apart.
    """
    e = np.zeros((N_SKUS, N_SKUS), dtype=np.float64)
    for i, si in enumerate(SKUS):
        e[i, i] = OWN_ELASTICITY_BY_FORMAT[si["format"]].value
        for j, sj in enumerate(SKUS):
            if i == j:
                continue
            e[i, j] = (
                CROSS_ELASTICITY_WITHIN_BRAND.value
                if si["brand"] == sj["brand"]
                else CROSS_ELASTICITY_ACROSS_BRAND.value
            )
    return e


def promo_lift_log(depth_pct: np.ndarray, mechanic: np.ndarray) -> np.ndarray:
    """log-volume promo lift: b_promo * (1-exp(-k*depth)) * mechanic_multiplier.

    `depth_pct` in [0,100], `mechanic` an array of strings from PROMO_MECHANICS.
    Vectorised; `mechanic == "none"` forces zero lift regardless of depth.
    """
    depth = np.asarray(depth_pct, dtype=np.float64) / 100.0
    k = PROMO_SATURATION_K.value
    b = PROMO_LIFT_SCALE.value
    sat = 1.0 - np.exp(-k * depth)
    mult = np.ones_like(depth)
    for name, a in PROMO_MECHANIC_MULTIPLIER.items():
        mult = np.where(np.asarray(mechanic) == name, a.value, mult)
    mult = np.where(np.asarray(mechanic) == "none", 0.0, mult)
    return b * sat * mult


# --- Generator-only seeds (never read by the engine; no Assumption id) -
GENERATOR_SEED = {
    # Base store-week volume at price_index=1, no promo, no seasonality (units).
    # A format-level seed, not a registry assumption: it only shapes the
    # synthetic history and is superseded, for the engine, by the
    # data-derived baseline computed in Phase 2 from this generated data.
    "base_volume_by_format": {
        "can_330ml": 180.0,
        "pet_500ml": 140.0,
        "bottle_1500ml": 60.0,
        "multipack_6x330ml": 40.0,
    },
    # Reference (list) price per unit, $ at price_index=1.0.
    "list_price_by_format": {
        "can_330ml": 0.60,
        "pet_500ml": 0.85,
        "bottle_1500ml": 1.80,
        "multipack_6x330ml": 3.20,
    },
    # Brand price tier: premium / mainstream / value.
    "brand_price_multiplier": {"Aurora": 1.05, "Boreal": 1.00, "Comet": 0.92, "Delta": 1.10, "Ember": 0.85},
    "seasonality_amplitude": 0.05,  # log-scale sinusoidal amplitude, 52-week period
    "region_week_noise_sigma": 0.03,  # common shock per (sku, region, week)
    "store_noise_sigma": 0.08,  # idiosyncratic per (sku, region, store, week)
    "price_index_walk_sigma": 0.01,  # weekly drift step for price_index
    "price_index_bounds": (0.88, 1.12),
}


# --- Synthetic consumer generator-only inputs (no Assumption id) ---------
# Same status as GENERATOR_SEED: they shape the *synthetic* respondents and
# are never read by the engine. Research methods read the registry above.
CONSUMER_GENERATOR_SEED = {
    "segments": ("value_seeker", "family_planner", "brand_loyal", "deal_responsive"),
    "price_sensitivity_mean": {"value_seeker": 0.82, "family_planner": 0.45, "brand_loyal": 0.24, "deal_responsive": 0.68},
    "promotion_sensitivity_mean": {"value_seeker": 0.45, "family_planner": 0.30, "brand_loyal": 0.20, "deal_responsive": 0.85},
    "sensitivity_sigma": {"price": 0.08, "promotion": 0.07},
    "pack_mix": [0.32, 0.30, 0.22, 0.16],  # follows FORMATS order
    "age_bands": ["18-24", "25-34", "35-44", "45-54", "55+"],
    "age_mix": [0.15, 0.28, 0.25, 0.18, 0.14],
    "purchase_frequency": ["weekly", "2-3x_month", "monthly"],
    "purchase_frequency_mix": [0.45, 0.40, 0.15],
    "wtp_premium_at_zero_sensitivity": 0.12,
    "wtp_sensitivity_slope": 0.16,
    "wtp_noise_sigma": 0.035,
    # Van Westendorp answers as multiples of a respondent's WTP, sorted per respondent.
    "vw_factors": {"too_cheap": 0.70, "cheap": 0.85, "expensive": 1.12, "too_expensive": 1.30},
    "vw_noise_sigma": 0.04,
    "promo_comment_threshold": 0.72,
    "low_price_sensitivity_comment_threshold": 0.35,
}
