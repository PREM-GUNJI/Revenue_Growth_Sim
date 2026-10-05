"""AC-004: back-test error within tolerance; sensitivity ranking stable across seeds."""

import numpy as np

from backend.data.generator import generate
from backend.model.backtest import (
    _reference_scenario_metric,
    run_backtest,
    run_tornado,
)
from backend.model.baselines import national_weekly_series
from backend.model.envelope_build import build_joint_coverage
from backend.model.spec import build_param_draws

MAPE_TOLERANCE = 0.15  # 15%: a consistency check, not a precision claim


def test_backtest_mape_within_tolerance():
    draws = build_param_draws(k=50, seed=1000)
    result = run_backtest(draws)
    assert result["mape"] < MAPE_TOLERANCE


def test_backtest_band_coverage_is_reported_and_bounded():
    draws = build_param_draws(k=50, seed=1000)
    result = run_backtest(draws)
    assert 0.0 <= result["band_coverage"] <= 1.0


def test_sensitivity_ranking_stable_across_seeds():
    rank_a = [aid for aid, _ in run_tornado(_reference_scenario_metric, k=50, seed=1000)]
    rank_b = [aid for aid, _ in run_tornado(_reference_scenario_metric, k=50, seed=2000)]
    assert rank_a == rank_b


def test_tornado_top_assumption_has_nonzero_spread():
    ranking = run_tornado(_reference_scenario_metric, k=50, seed=1000)
    assert ranking[0][1] > 0


def test_joint_coverage_gap_region_is_empty():
    df = generate(42)
    jc = build_joint_coverage(df)
    deep_depth_idx = [i for i, d in enumerate(jc.depth_steps) if d > 20]
    high_price_idx = [i for i, e in enumerate(jc.price_bin_edges[:-1]) if e >= 1.06]
    gap = jc.counts[:, :, deep_depth_idx[0] :, high_price_idx[0] :]
    assert gap.sum() == 0


def test_national_weekly_series_row_count():
    df = generate(42)
    weekly = national_weekly_series(df)
    from backend.assumptions.assumptions import N_SKUS, N_WEEKS

    assert len(weekly) == N_SKUS * N_WEEKS


def test_baseline_volumes_are_positive():
    draws = build_param_draws(k=10, seed=1000)
    result = run_backtest(draws)
    assert all(v > 0 for v in result["baselines"].baseline_volume.values())


def test_draws_npz_roundtrip(tmp_path):
    from backend.model.backtest import write_report

    write_report(out_dir=tmp_path / "reports", draws_dir=tmp_path / "data_out")
    loaded = np.load(tmp_path / "data_out" / "draws.npz")
    assert loaded["elasticity"].shape[0] == 201  # central + K=200
    assert (tmp_path / "reports" / "model_backtest.md").exists()
