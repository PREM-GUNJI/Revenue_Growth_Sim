"""Support-envelope inputs (PLAN.md section 6): a binned joint-occupancy
count table over (format, mechanic, promo depth, price index), computed
from the raw generated dataset only (descriptive statistics, no fitting).

Phase 5's `backend/engine/support.py` turns these counts into REFUSED /
EDGE / SUPPORTED decisions. This module only builds the counts.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.assumptions.assumptions import FORMATS, PROMO_DEPTH_STEPS, PROMO_MECHANICS

N_PRICE_BINS = 12
PRICE_BIN_EDGES = np.linspace(0.88, 1.12, N_PRICE_BINS + 1)


@dataclass
class JointCoverage:
    """counts[format_idx, mechanic_idx, depth_idx, price_bin_idx] = row count.

    Brands and regions are pooled within each format (PLAN.md's "pool
    brands and regions within a format" — formats are the only categorical
    axis that matters for substitution/refusal, not the specific brand).
    """

    counts: np.ndarray  # (4, 4, 7, 12) uint32
    formats: list[str]
    mechanics: list[str]
    depth_steps: list[int]
    price_bin_edges: np.ndarray


def build_joint_coverage(df: pd.DataFrame) -> JointCoverage:
    price_bin = np.clip(
        np.digitize(df["price_index"].to_numpy(), PRICE_BIN_EDGES[1:-1]), 0, N_PRICE_BINS - 1
    )
    depth_idx = df["promo_depth_pct"].map({d: i for i, d in enumerate(PROMO_DEPTH_STEPS)})
    format_idx = df["format"].map({f: i for i, f in enumerate(FORMATS)})
    mechanic_idx = df["promo_mechanic"].map({m: i for i, m in enumerate(PROMO_MECHANICS)})

    counts = np.zeros(
        (len(FORMATS), len(PROMO_MECHANICS), len(PROMO_DEPTH_STEPS), N_PRICE_BINS), dtype=np.uint32
    )
    np.add.at(
        counts,
        (
            format_idx.to_numpy(),
            mechanic_idx.to_numpy(),
            depth_idx.to_numpy(),
            price_bin,
        ),
        1,
    )
    return JointCoverage(
        counts=counts,
        formats=FORMATS,
        mechanics=PROMO_MECHANICS,
        depth_steps=PROMO_DEPTH_STEPS,
        price_bin_edges=PRICE_BIN_EDGES,
    )
