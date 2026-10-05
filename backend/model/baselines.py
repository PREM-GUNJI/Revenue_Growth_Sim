"""Data-derived descriptive statistics (PLAN.md section 4): baseline volume
per SKU, national weekly series, and per-lever supported ranges. Computed
from the generated dataset only — nothing here is fitted or learned; the
"de-trending" below just backs out the registry's own (already-fixed,
modelling-choice) price/promo effects to get a clean volume intercept.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.assumptions.assumptions import N_WEEKS, SKU_IDS
from backend.model.spec import (
    ParamDraws,
    cross_price_log_effect,
    promo_lift_log_draws,
)

BACKTEST_WINDOW_WEEKS = 13


def national_weekly_series(df: pd.DataFrame) -> pd.DataFrame:
    """Collapses (sku, region, store, week) rows to one row per (sku, week):
    national total volume, and a volume-weighted-average price index. Promo
    depth is volume-weighted-averaged too; the mechanic is whichever
    region/week had the deepest promo (dominant mechanic that week).
    """

    def _agg(g: pd.DataFrame) -> pd.Series:
        region_vol = g.groupby("region")["units_sold"].sum()
        region_price = g.groupby("region")["price_index"].mean()
        region_depth = g.groupby("region")["promo_depth_pct"].mean()
        w = region_vol.reindex(region_price.index).fillna(0.0)
        total_w = w.sum()
        weighted_price = (region_price * w).sum() / total_w if total_w > 0 else region_price.mean()
        weighted_depth = (region_depth * w).sum() / total_w if total_w > 0 else 0.0

        deepest_region = region_depth.idxmax() if region_depth.max() > 0 else None
        mechanic = (
            g.loc[g["region"] == deepest_region, "promo_mechanic"].mode().iat[0]
            if deepest_region is not None
            else "none"
        )
        return pd.Series(
            {
                "national_volume": g["units_sold"].sum(),
                "price_index": weighted_price,
                "promo_depth_pct": weighted_depth,
                "promo_mechanic": mechanic,
            }
        )

    out = df.groupby(["sku_id", "week"], observed=True).apply(_agg, include_groups=False)
    return out.reset_index()


@dataclass
class Baselines:
    baseline_volume: dict[str, float]  # per sku_id, national units/week
    price_index_p1_p99: dict[str, tuple[float, float]]
    promo_depth_observed: list[int]
    formats_observed: list[str]
    mechanics_observed: list[str]


def compute_baselines(weekly: pd.DataFrame, raw_df: pd.DataFrame, draws: ParamDraws) -> Baselines:
    """Baseline volume = de-trended mean over the last BACKTEST_WINDOW_WEEKS
    weeks: back out the (fixed, registry) price/promo effect from each
    week's actual volume, then average the implied intercept.
    """
    pivot_price = weekly.pivot(index="week", columns="sku_id", values="price_index")[SKU_IDS]
    pivot_depth = weekly.pivot(index="week", columns="sku_id", values="promo_depth_pct")[SKU_IDS]
    pivot_mech = weekly.pivot(index="week", columns="sku_id", values="promo_mechanic")[SKU_IDS]
    pivot_vol = weekly.pivot(index="week", columns="sku_id", values="national_volume")[SKU_IDS]

    # Back-testing reconstructs each actual week's own volume from that
    # week's own realised price/promo, so it uses the direct per-week promo
    # lift (not the scenario-side "weeks_per_month" steady-state average).
    # Known limitation: the week right after a real promo event carries the
    # generator's pull-forward dip, which isn't separately observable in
    # this aggregated weekly series, so those weeks show somewhat higher
    # error — stated in the back-test report rather than modelled around.
    ln_price = np.log(pivot_price.to_numpy())  # (N_WEEKS, N_SKUS)
    cross = cross_price_log_effect(ln_price, draws.elasticity)[0]  # central draw, (N_WEEKS, N_SKUS)
    promo_effect = promo_lift_log_draws(pivot_depth.to_numpy(), pivot_mech.to_numpy(), draws)[0]

    last_n = slice(N_WEEKS - BACKTEST_WINDOW_WEEKS, N_WEEKS)
    implied_a = np.log(pivot_vol.to_numpy()[last_n]) - cross[last_n] - promo_effect[last_n]
    baseline_volume = np.exp(implied_a.mean(axis=0))

    return Baselines(
        baseline_volume=dict(zip(SKU_IDS, baseline_volume, strict=True)),
        price_index_p1_p99={
            sku: (
                float(np.percentile(raw_df.loc[raw_df.sku_id == sku, "price_index"], 1)),
                float(np.percentile(raw_df.loc[raw_df.sku_id == sku, "price_index"], 99)),
            )
            for sku in SKU_IDS
        },
        promo_depth_observed=sorted(raw_df["promo_depth_pct"].unique().tolist()),
        formats_observed=sorted(raw_df["format"].unique().tolist()),
        mechanics_observed=sorted(raw_df["promo_mechanic"].unique().tolist()),
    )
