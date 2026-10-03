"""Builds reports/model_backtest.md and model/draws.npz (PLAN.md section 4).

Because the generator shares the same assumption set as the engine, this
is a CONSISTENCY check (does the implementation reproduce its own
generating model within noise?), not a validation against real-world
accuracy. That distinction is stated in the generated report itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.assumptions.assumptions import ASSUMPTIONS, N_WEEKS, SKU_IDS
from backend.data.generator import generate
from backend.model.baselines import BACKTEST_WINDOW_WEEKS, compute_baselines, national_weekly_series
from backend.model.spec import (
    DRAWABLE_ASSUMPTION_IDS,
    average_monthly_promo_log_effect,
    build_param_draws,
    cross_price_log_effect,
    promo_lift_log_draws,
)

DRAWS_K = 200
DRAWS_SEED = 1000
TORNADO_SEED = 1000


def spec_hash() -> str:
    """Hash of every registered assumption's (value, valid_range) — detects
    drift between draws.npz and the current assumptions module."""
    payload = {
        aid: {"value": a.value, "valid_range": a.valid_range}
        for aid, a in sorted(ASSUMPTIONS.items())
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _predict_national_volume(weekly: pd.DataFrame, baseline_volume: dict, draws, draw_idx: int = 0):
    pivot_price = weekly.pivot(index="week", columns="sku_id", values="price_index")[SKU_IDS]
    pivot_depth = weekly.pivot(index="week", columns="sku_id", values="promo_depth_pct")[SKU_IDS]
    pivot_mech = weekly.pivot(index="week", columns="sku_id", values="promo_mechanic")[SKU_IDS]

    ln_price = np.log(pivot_price.to_numpy())
    cross = cross_price_log_effect(ln_price, draws.elasticity)  # (K+1, N_WEEKS, N_SKUS)
    promo = promo_lift_log_draws(pivot_depth.to_numpy(), pivot_mech.to_numpy(), draws)

    base = np.log(np.array([baseline_volume[s] for s in SKU_IDS]))
    ln_pred = base[None, None, :] + cross + promo  # (K+1, N_WEEKS, N_SKUS)
    return np.exp(ln_pred), pivot_price.index.to_numpy()


def run_backtest(draws) -> dict:
    df = generate(42)
    weekly = national_weekly_series(df)
    baselines = compute_baselines(weekly, df, draws)

    pred_all, weeks = _predict_national_volume(weekly, baselines.baseline_volume, draws)
    last_n = slice(N_WEEKS - BACKTEST_WINDOW_WEEKS, N_WEEKS)

    actual_pivot = weekly.pivot(index="week", columns="sku_id", values="national_volume")[SKU_IDS]
    actual = actual_pivot.to_numpy()[last_n]  # (13, N_SKUS)

    pred_central = pred_all[0, last_n]  # (13, N_SKUS)
    pred_bands = pred_all[1:, last_n]  # (K, 13, N_SKUS)

    ape = np.abs(pred_central - actual) / actual
    mape = float(ape.mean())

    p10 = np.percentile(pred_bands, 10, axis=0)
    p90 = np.percentile(pred_bands, 90, axis=0)
    coverage = float(((actual >= p10) & (actual <= p90)).mean())

    return {
        "mape": mape,
        "band_coverage": coverage,
        "n_points": int(actual.size),
        "baselines": baselines,
    }


def run_tornado(metric_fn, k: int = 50, seed: int = TORNADO_SEED) -> list[tuple[str, float]]:
    """One-at-a-time sensitivity: for each assumption, vary only it across
    `k` draws (others held central) and rank by the resulting spread of
    `metric_fn(draws) -> np.ndarray of shape (k+1,)`.
    """
    results = []
    for aid in DRAWABLE_ASSUMPTION_IDS:
        draws = build_param_draws(k=k, seed=seed, vary_only=aid)
        metric = metric_fn(draws)
        # Spread as % of the central value — the metric's raw units aren't
        # meaningful (this reference scenario has no baseline-volume scale),
        # but the relative movement is comparable across assumptions.
        spread_pct = float((metric[1:].max() - metric[1:].min()) / metric[0] * 100.0)
        results.append((aid, spread_pct))
    return sorted(results, key=lambda x: -x[1])


def _reference_scenario_metric(draws) -> np.ndarray:
    """Total portfolio volume at a "stress" reference scenario: +8% price and
    a half-month promo (15% depth) on every SKU, cycling the three mechanics
    across SKUs so every mechanic multiplier is exercised. A price_index=1.0,
    no-promo scenario would make this metric degenerate — ln(1.0)=0 and
    depth=0 zero out every price and promo term regardless of the
    assumption's value, so no assumption could ever show a spread.
    """
    n = len(SKU_IDS)
    ln_price = np.full((1, n), np.log(1.08))
    mechanics_cycle = ["TPR", "feature_display", "BOGO"]
    mech = np.array([[mechanics_cycle[i % 3] for i in range(n)]], dtype=object)
    depth = np.full((1, n), 15.0)
    weeks_per_month = np.full((1, n), 2.0)

    cross = cross_price_log_effect(ln_price, draws.elasticity)[:, 0, :]  # (K+1, N_SKUS)
    promo = average_monthly_promo_log_effect(depth, mech, weeks_per_month, draws)[:, 0, :]
    return np.exp(cross + promo).sum(axis=1)  # (K+1,) total units across the portfolio


def write_report(out_dir: Path = Path("reports"), draws_dir: Path = Path("data")) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    draws_dir.mkdir(parents=True, exist_ok=True)

    draws = build_param_draws(k=DRAWS_K, seed=DRAWS_SEED)
    bt = run_backtest(draws)

    tornado_seed_a = run_tornado(_reference_scenario_metric, k=50, seed=1000)
    tornado_seed_b = run_tornado(_reference_scenario_metric, k=50, seed=2000)
    rank_a = [aid for aid, _ in tornado_seed_a]
    rank_b = [aid for aid, _ in tornado_seed_b]
    rank_stable = rank_a == rank_b

    # Save draws.npz
    mech = draws.mech_mult
    np.savez(
        draws_dir / "draws.npz",
        elasticity=draws.elasticity,
        promo_k=draws.promo_k,
        promo_b=draws.promo_b,
        mech_mult_TPR=mech["TPR"],
        mech_mult_feature_display=mech["feature_display"],
        mech_mult_BOGO=mech["BOGO"],
        pull_forward_share=draws.pull_forward_share,
    )
    data_manifest = json.loads(Path("data/data_manifest.json").read_text())
    draws_manifest = {
        "k": draws.k,
        "seed": draws.seed,
        "data_sha256": data_manifest["data_sha256"],
        "spec_hash": spec_hash(),
    }
    (draws_dir / "draws_manifest.json").write_text(
        json.dumps(draws_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# Model back-test and sensitivity report",
        "",
        "**This is a consistency check, not a validation of real-world accuracy.** "
        "The data generator (`backend/data/generator.py`) and the engine's demand "
        "spec (`backend/model/spec.py`) share the exact same assumption values "
        "(`backend/assumptions/assumptions.py`). A back-test here can only confirm "
        "that the implementation reproduces its own generating model within the "
        "data's noise level — it says nothing about real-world accuracy, which "
        "would require real data and a calibration step (see docs/HONESTY.md).",
        "",
        "## Back-test: last 13 weeks, held out from the baseline-volume calculation's "
        "own averaging window only in the sense that each week is predicted from the "
        "*window average* baseline, not from itself alone",
        "",
        f"- Points: {bt['n_points']} ({BACKTEST_WINDOW_WEEKS} weeks x {len(SKU_IDS)} SKUs)",
        f"- MAPE (central-draw prediction vs actual national weekly volume): {bt['mape']:.1%}",
        f"- P10-P90 band coverage (K={DRAWS_K} draws): {bt['band_coverage']:.1%}",
        "",
        "Known limitation: the week immediately after a real promo event carries the "
        "generator's pull-forward dip, which isn't separately observable in the "
        "aggregated national weekly series used here, so those specific weeks carry "
        "above-average error. This is a modelling simplification of the back-test "
        "reconstruction, not a bug in the engine's scenario-evaluation formula "
        "(which receives `weeks_per_month` explicitly and does not need to infer it).",
        "",
        "## Sensitivity (one-at-a-time tornado)",
        "",
        "Metric: total portfolio volume at a reference stress scenario (+8% price "
        "and a half-month, 15%-depth promo on every SKU, mechanics cycled across "
        "SKUs), varying one assumption at a time across its registry `valid_range` "
        "(k=50 draws), others held at their central value. Spread is reported as "
        "% change relative to the central-value metric, since the reference "
        "scenario has no baseline-volume scale of its own (Phase 4 adds margin, "
        "which gives sensitivity a real-dollar scale).",
        "",
        "| Rank | Assumption | Label | Spread (% of central) |",
        "|---|---|---|---|",
    ]
    for rank, (aid, spread_pct) in enumerate(tornado_seed_a, start=1):
        label = ASSUMPTIONS[aid].label
        lines.append(f"| {rank} | {aid} | {label} | {spread_pct:.1f}% |")
    lines += [
        "",
        f"**Ranking stability across seeds (1000 vs 2000): "
        f"{'stable (identical order)' if rank_stable else 'NOT stable — see raw ranks below'}.**",
    ]
    if not rank_stable:
        lines += [
            f"- seed 1000 order: {rank_a}",
            f"- seed 2000 order: {rank_b}",
        ]
    lines += [
        "",
        "## Baseline volumes (data-derived, national units/week, last 13 weeks de-trended)",
        "",
        "| SKU | Baseline volume |",
        "|---|---|",
    ]
    for sku, vol in bt["baselines"].baseline_volume.items():
        lines.append(f"| {sku} | {vol:,.1f} |")

    (out_dir / "model_backtest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_report()
    print("wrote reports/model_backtest.md and data/draws.npz")
