"""The parametric demand function (PLAN.md section 4). Nothing is fitted.

Pure math, vectorised, no I/O and no randomness of its own — callers pass
in whichever parameter arrays they want (the registered central values, or
a stack of K Monte Carlo draws built by `build_param_draws`).

Shapes follow the Phase 0.5 spike (a) design: a leading draw axis of size
K+1 (index 0 = central, 1..K = draws), so the same functions serve both a
single central evaluation and a full sensitivity-band computation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.assumptions import registry
from backend.assumptions.assumptions import (
    ASSUMPTIONS,
    CROSS_ELASTICITY_ACROSS_BRAND,
    CROSS_ELASTICITY_WITHIN_BRAND,
    N_SKUS,
    OWN_ELASTICITY_BY_FORMAT,
    PROMO_LIFT_SCALE,
    PROMO_MECHANIC_MULTIPLIER,
    PROMO_SATURATION_K,
    PULL_FORWARD_SHARE,
    SKUS,
)

# Only `.id` is used from the imports above — every *value* is read through
# `registry.get()` below so reads are tracked (CLAUDE.md engine rule).

# Order matters only for reproducibility of the draws array's column layout.
DRAWABLE_ASSUMPTION_IDS: list[str] = [
    *[OWN_ELASTICITY_BY_FORMAT[s["format"]].id for s in SKUS[:4]],  # one per format (4)
    CROSS_ELASTICITY_WITHIN_BRAND.id,
    CROSS_ELASTICITY_ACROSS_BRAND.id,
    PROMO_SATURATION_K.id,
    PROMO_LIFT_SCALE.id,
    PROMO_MECHANIC_MULTIPLIER["TPR"].id,
    PROMO_MECHANIC_MULTIPLIER["feature_display"].id,
    PROMO_MECHANIC_MULTIPLIER["BOGO"].id,
    PULL_FORWARD_SHARE.id,
]
assert len(DRAWABLE_ASSUMPTION_IDS) == len(set(DRAWABLE_ASSUMPTION_IDS)) == 12


@dataclass
class ParamDraws:
    """(K+1, ...) stacks of every parameter the demand function needs.

    Index 0 is always the central (registered) value; 1..K are Monte Carlo
    draws, each sampled uniformly within that assumption's `valid_range`.
    """

    k: int  # number of draws (not counting the central row)
    seed: int
    elasticity: np.ndarray  # (K+1, N_SKUS, N_SKUS)
    promo_k: np.ndarray  # (K+1,)
    promo_b: np.ndarray  # (K+1,)
    mech_mult: dict[str, np.ndarray]  # each (K+1,)
    pull_forward_share: np.ndarray  # (K+1,)

    @property
    def k_plus_1(self) -> int:
        return self.k + 1


def _draw_or_central(rng: np.random.Generator, assumption, k: int) -> np.ndarray:
    lo, hi = assumption.valid_range
    out = np.empty(k + 1)
    out[0] = assumption.value
    out[1:] = rng.uniform(lo, hi, size=k)
    return out


def _central(assumption, k: int) -> np.ndarray:
    return np.full(k + 1, assumption.value, dtype=np.float64)


def build_param_draws(k: int = 200, seed: int = 1000, vary_only: str | None = None) -> ParamDraws:
    """Draws every drawable assumption within its registry range (fixed seed).

    `vary_only`: if set to one assumption id, every OTHER assumption is held
    at its central value across all K+1 rows, and only this one is drawn —
    used for one-at-a-time sensitivity (the back-test's tornado ranking).
    """
    rng = np.random.default_rng(seed)

    def draw(assumption_id: str) -> np.ndarray:
        assumption = registry.get(assumption_id)  # tracked read (CLAUDE.md engine rule)
        if vary_only is None or assumption_id == vary_only:
            return _draw_or_central(rng, assumption, k)
        return _central(assumption, k)

    own_by_format = {
        fmt: draw(OWN_ELASTICITY_BY_FORMAT[fmt].id) for fmt in OWN_ELASTICITY_BY_FORMAT
    }
    within = draw(CROSS_ELASTICITY_WITHIN_BRAND.id)
    across = draw(CROSS_ELASTICITY_ACROSS_BRAND.id)

    elasticity = np.zeros((k + 1, N_SKUS, N_SKUS))
    for i, si in enumerate(SKUS):
        elasticity[:, i, i] = own_by_format[si["format"]]
        for j, sj in enumerate(SKUS):
            if i == j:
                continue
            elasticity[:, i, j] = within if si["brand"] == sj["brand"] else across

    promo_k = draw(PROMO_SATURATION_K.id)
    promo_b = draw(PROMO_LIFT_SCALE.id)
    mech_mult = {name: draw(a.id) for name, a in PROMO_MECHANIC_MULTIPLIER.items()}
    pull_forward_share = draw(PULL_FORWARD_SHARE.id)

    return ParamDraws(
        k=k,
        seed=seed,
        elasticity=elasticity,
        promo_k=promo_k,
        promo_b=promo_b,
        mech_mult=mech_mult,
        pull_forward_share=pull_forward_share,
    )


def cross_price_log_effect(ln_price_index: np.ndarray, elasticity: np.ndarray) -> np.ndarray:
    """own+cross price log-effect. Folds both into one matmul per draw.

    ln_price_index: (..., N_SKUS)   elasticity: (K+1, N_SKUS, N_SKUS)
    returns: (K+1, ..., N_SKUS)
    """
    # (K+1, N_SKUS, N_SKUS) @ (..., N_SKUS) via einsum, broadcasting leading dims.
    return np.einsum("kij,...j->k...i", elasticity, ln_price_index)


def promo_lift_log_draws(
    depth_pct: np.ndarray,
    mechanic: np.ndarray,
    draws: ParamDraws,
) -> np.ndarray:
    """Saturating promo lift in log space, for every draw at once.

    depth_pct, mechanic: broadcastable arrays, e.g. (..., N_SKUS).
    returns: (K+1, ...) matching depth_pct's shape with a leading draw axis.
    """
    depth = np.asarray(depth_pct, dtype=np.float64) / 100.0
    mechanic = np.asarray(mechanic)

    k = draws.promo_k[:, *([None] * depth.ndim)]
    b = draws.promo_b[:, *([None] * depth.ndim)]
    sat = 1.0 - np.exp(-k * depth[None, ...])

    mult = np.ones((draws.k_plus_1, *depth.shape))
    for name, mult_draws in draws.mech_mult.items():
        sel = mechanic == name
        mult = np.where(sel[None, ...], mult_draws[:, *([None] * depth.ndim)], mult)
    mult = np.where((mechanic == "none")[None, ...], 0.0, mult)

    return b * sat * mult


def average_monthly_promo_log_effect(
    depth_pct: np.ndarray,
    mechanic: np.ndarray,
    weeks_per_month: np.ndarray,
    draws: ParamDraws,
) -> np.ndarray:
    """Steady-state weekly log-effect of running a promo `weeks_per_month`
    weeks out of every 4, net of one post-promo pull-forward dip per month.

    Used by scenario evaluation (a static lever, not a time series): a
    scenario with weeks_per_month=0 gets zero effect regardless of depth.
    """
    lift = promo_lift_log_draws(depth_pct, mechanic, draws)  # (K+1, ...)
    weeks = np.asarray(weeks_per_month, dtype=np.float64)
    has_promo = (weeks > 0)[None, ...]
    pf = draws.pull_forward_share[:, *([None] * weeks.ndim)]
    dip_events_per_month = np.where(has_promo, 1.0, 0.0)
    return lift * (weeks[None, ...] - pf * dip_events_per_month) / 4.0


def registry_coverage_ids() -> set[str]:
    """All assumption ids this module can read from (for Phase 3's coverage test)."""
    return set(DRAWABLE_ASSUMPTION_IDS) | set(ASSUMPTIONS.keys())
