"""Synthetic CPG scanner-data generator (PLAN.md section 3).

Ground-truth generating model, per (SKU, region, week):

    ln Q = ln(base_volume_sku)
           + e_own * ln(price_index)                 -- own-price term
           + sum_j e_cross_ij * ln(price_index_j)    -- cross-price terms
           (both folded into one matmul against the elasticity matrix)
           + promo_lift_log(depth, mechanic)          -- saturating promo lift
           - pull_forward_dip                         -- post-promo dip
           + seasonality(week)                        -- stationary, 52-week period
           + region_week_noise                        -- shared shock per region-week
           + store_noise                              -- idiosyncratic per store-week

Then `units_sold = round(exp(ln Q) * store_noise_multiplier)` per store.
Noise and seasonality exist ONLY here, never in the engine (CLAUDE.md).

Deliberate joint-support gap (documented for the refusal suite, mirrored
into data_manifest.json verbatim):

    GAP-1: no row has price_index > 1.06 together with promo_depth_pct > 20,
           for the same (sku, region, week).

This dataset is pure "scanner" fact (price, promo, volume) — manufacturer
cost/margin fields are NOT generated here; they are applied by the engine
from the assumptions registry (real scanner panels don't carry a
manufacturer's cost structure either).

All randomness flows through one seeded `numpy.random.Generator` passed
explicitly. No global RNG state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backend.assumptions.assumptions import (
    CURRENCY_CODE,
    GENERATOR_SEED,
    N_SKUS,
    N_WEEKS,
    PROMO_DEPTH_STEPS,
    PULL_FORWARD_SHARE,
    REGIONS,
    SKUS,
    STORES_PER_REGION,
    build_elasticity_matrix,
    promo_lift_log,
)

GENERATOR_VERSION = "1.1.0"  # 1.1.0: unit_price is in INR (was an unlabelled "$" scale)

DECLARED_GAPS = [
    "price_index > 1.06 and promo_depth_pct > 20 (for the same sku, region, week)",
]

_MECH_CHOICES = ["TPR", "feature_display", "BOGO"]
_MECH_WEIGHTS = [0.6, 0.3, 0.1]
_DEPTH_CHOICES = PROMO_DEPTH_STEPS[1:]  # 5..30, excludes 0 (no-promo weeks)
_DEPTH_WEIGHTS = np.array([5, 4, 3, 2, 2, 1], dtype=float)
_DEPTH_WEIGHTS /= _DEPTH_WEIGHTS.sum()
_PROMO_START_PROB = 0.12
_GAP_PRICE_MAX = 1.06
_GAP_DEPTH_MIN = 20


def _simulate_promo_calendar(
    rng: np.random.Generator, n_weeks: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-SKU-region promo event calendar: returns (depth_pct, mechanic, dip)."""
    depth = np.zeros(n_weeks, dtype=np.float64)
    mechanic = np.full(n_weeks, "none", dtype=object)
    dip = np.zeros(n_weeks, dtype=np.float64)

    t = 0
    while t < n_weeks:
        if rng.random() < _PROMO_START_PROB:
            length = int(rng.integers(1, 4))  # 1, 2 or 3 weeks
            d = float(rng.choice(_DEPTH_CHOICES, p=_DEPTH_WEIGHTS))
            m = str(rng.choice(_MECH_CHOICES, p=_MECH_WEIGHTS))
            end = min(t + length, n_weeks)
            depth[t:end] = d
            mechanic[t:end] = m
            if end < n_weeks:
                lift = float(promo_lift_log(np.array([d]), np.array([m]))[0])
                dip[end] = PULL_FORWARD_SHARE.value * lift
            t = end
        else:
            t += 1
    return depth, mechanic, dip


def _simulate_price_index(rng: np.random.Generator, n_weeks: int) -> np.ndarray:
    lo, hi = GENERATOR_SEED["price_index_bounds"]
    sigma = GENERATOR_SEED["price_index_walk_sigma"]
    steps = rng.normal(0.0, sigma, size=n_weeks)
    walk = 1.0 + np.cumsum(steps)
    return np.clip(walk, lo, hi)


def _enforce_gap(
    rng: np.random.Generator, price_index: np.ndarray, depth_pct: np.ndarray
) -> np.ndarray:
    """Redraws price_index (only) wherever it violates the declared GAP-1."""
    price_index = price_index.copy()
    # price_index is rounded to 4 dp in the output, so compare the rounded value: 1.05996 would land on the 1.06 bin edge
    violated = (np.round(price_index, 4) >= _GAP_PRICE_MAX) & (depth_pct > _GAP_DEPTH_MIN)
    n = int(violated.sum())
    if n:
        # stop 0.001 short of the cap: price_index is rounded to 4 dp later, and a draw rounding up to 1.06 sits on the bin edge
        price_index[violated] = rng.uniform(0.88, _GAP_PRICE_MAX - 0.001, size=n)
    return price_index


@dataclass
class _RegionSeries:
    price_index: np.ndarray  # (N_SKUS, N_WEEKS)
    depth_pct: np.ndarray
    mechanic: np.ndarray
    dip: np.ndarray


def _generate_region(rng: np.random.Generator) -> _RegionSeries:
    price_index = np.empty((N_SKUS, N_WEEKS))
    depth_pct = np.empty((N_SKUS, N_WEEKS))
    mechanic = np.empty((N_SKUS, N_WEEKS), dtype=object)
    dip = np.empty((N_SKUS, N_WEEKS))

    for i in range(N_SKUS):
        price_index[i] = _simulate_price_index(rng, N_WEEKS)
        d, m, dp = _simulate_promo_calendar(rng, N_WEEKS)
        depth_pct[i], mechanic[i], dip[i] = d, m, dp
        price_index[i] = _enforce_gap(rng, price_index[i], depth_pct[i])

    return _RegionSeries(price_index, depth_pct, mechanic, dip)


def _assert_no_gap_violations(df: pd.DataFrame) -> None:
    violated = (df["price_index"] > _GAP_PRICE_MAX) & (df["promo_depth_pct"] > _GAP_DEPTH_MIN)
    if violated.any():
        raise AssertionError(f"{int(violated.sum())} rows violate the declared GAP-1")


def generate(seed: int) -> pd.DataFrame:
    """Builds the full synthetic scanner dataset for the given seed."""
    rng = np.random.default_rng(seed)
    E = build_elasticity_matrix()
    amplitude = GENERATOR_SEED["seasonality_amplitude"]
    seasonality = amplitude * np.sin(2 * np.pi * np.arange(N_WEEKS) / 52.0)

    rows: list[pd.DataFrame] = []
    for region in REGIONS:
        series = _generate_region(rng)
        lnP = np.log(series.price_index).T  # (N_WEEKS, N_SKUS)
        cross = lnP @ E.T  # (N_WEEKS, N_SKUS); diagonal of E carries the own term
        promo = promo_lift_log(series.depth_pct, series.mechanic)  # (N_SKUS, N_WEEKS)

        region_week_noise = rng.normal(
            0.0, GENERATOR_SEED["region_week_noise_sigma"], size=(N_SKUS, N_WEEKS)
        )

        base_vol = np.array([GENERATOR_SEED["base_volume_by_format"][s["format"]] for s in SKUS])
        ln_q = (
            np.log(base_vol)[:, None]
            + cross.T  # (N_SKUS, N_WEEKS)
            + promo
            - series.dip
            + seasonality[None, :]
            + region_week_noise
        )
        expected_q = np.exp(ln_q)  # (N_SKUS, N_WEEKS), per-store expected units

        for si, sku in enumerate(SKUS):
            unit_price = (
                GENERATOR_SEED["list_price_by_format"][sku["format"]]
                * GENERATOR_SEED["brand_price_multiplier"][sku["brand"]]
                * series.price_index[si]
            )
            for store in range(1, STORES_PER_REGION + 1):
                store_noise = np.exp(
                    rng.normal(0.0, GENERATOR_SEED["store_noise_sigma"], size=N_WEEKS)
                )
                units = np.maximum(0, np.round(expected_q[si] * store_noise)).astype(np.int64)
                rows.append(
                    pd.DataFrame(
                        {
                            "week": np.arange(N_WEEKS, dtype=np.int32),
                            "region": region,
                            "store_id": f"{region[:1]}{store:02d}",
                            "sku_id": sku["sku_id"],
                            "brand": sku["brand"],
                            "format": sku["format"],
                            "price_index": np.round(series.price_index[si], 4),
                            "unit_price": np.round(unit_price, 4),
                            "promo_depth_pct": series.depth_pct[si].astype(np.int32),
                            "promo_mechanic": series.mechanic[si],
                            "units_sold": units,
                        }
                    )
                )

    df = pd.concat(rows, ignore_index=True)
    _assert_no_gap_violations(df)
    return df


def write_dataset(seed: int, out_dir: Path) -> dict:
    """Generates, writes `data.parquet` + `data_manifest.json` to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df = generate(seed)

    parquet_path = out_dir / "data.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    data_sha256 = hashlib.sha256(parquet_path.read_bytes()).hexdigest()

    manifest = {
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "currency": CURRENCY_CODE,
        "row_count": len(df),
        "data_sha256": data_sha256,
        "declared_gaps": DECLARED_GAPS,
        "skus": [s["sku_id"] for s in SKUS],
        "regions": REGIONS,
        "weeks": N_WEEKS,
        "stores_per_region": STORES_PER_REGION,
    }
    (out_dir / "data_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    import sys

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
    m = write_dataset(seed, out_dir)
    print(json.dumps(m, indent=2))
