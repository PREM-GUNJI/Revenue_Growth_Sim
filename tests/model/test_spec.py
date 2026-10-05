"""Unit tests for backend/model/spec.py: param-draw shapes and reproducibility."""

import numpy as np

from backend.assumptions.assumptions import N_SKUS
from backend.model.spec import (
    DRAWABLE_ASSUMPTION_IDS,
    average_monthly_promo_log_effect,
    build_param_draws,
    cross_price_log_effect,
    promo_lift_log_draws,
)


def test_draws_shapes():
    d = build_param_draws(k=10, seed=1)
    assert d.elasticity.shape == (11, N_SKUS, N_SKUS)
    assert d.promo_k.shape == (11,)
    assert d.pull_forward_share.shape == (11,)
    for m in d.mech_mult.values():
        assert m.shape == (11,)


def test_draws_central_row_matches_registered_values():
    from backend.assumptions.assumptions import OWN_ELASTICITY_BY_FORMAT, SKUS

    d = build_param_draws(k=10, seed=1)
    for i, s in enumerate(SKUS):
        assert d.elasticity[0, i, i] == OWN_ELASTICITY_BY_FORMAT[s["format"]].value


def test_draws_reproducible_same_seed():
    d1 = build_param_draws(k=50, seed=7)
    d2 = build_param_draws(k=50, seed=7)
    assert np.array_equal(d1.elasticity, d2.elasticity)
    assert np.array_equal(d1.promo_k, d2.promo_k)


def test_draws_differ_different_seed():
    d1 = build_param_draws(k=50, seed=7)
    d2 = build_param_draws(k=50, seed=8)
    assert not np.array_equal(d1.elasticity, d2.elasticity)


def test_vary_only_holds_others_central():
    d = build_param_draws(k=20, seed=1, vary_only="A-007")
    assert np.all(d.promo_b == d.promo_b[0])  # held central
    assert not np.all(d.promo_k == d.promo_k[0])  # varies


def test_cross_price_log_effect_zero_at_reference_price():
    d = build_param_draws(k=5, seed=1)
    ln_price = np.zeros((3, N_SKUS))  # price_index == 1.0 everywhere
    cross = cross_price_log_effect(ln_price, d.elasticity)
    assert np.allclose(cross, 0.0)


def test_promo_lift_zero_when_mechanic_none():
    d = build_param_draws(k=5, seed=1)
    depth = np.full((2, N_SKUS), 20.0)
    mech = np.full((2, N_SKUS), "none", dtype=object)
    lift = promo_lift_log_draws(depth, mech, d)
    assert np.allclose(lift, 0.0)


def test_average_monthly_effect_zero_weeks_is_zero():
    d = build_param_draws(k=5, seed=1)
    depth = np.full((2, N_SKUS), 20.0)
    mech = np.full((2, N_SKUS), "BOGO", dtype=object)
    weeks = np.zeros((2, N_SKUS))
    effect = average_monthly_promo_log_effect(depth, mech, weeks, d)
    assert np.allclose(effect, 0.0)


def test_all_drawable_ids_are_registered():
    from backend.assumptions.assumptions import ASSUMPTIONS

    for aid in DRAWABLE_ASSUMPTION_IDS:
        assert aid in ASSUMPTIONS
