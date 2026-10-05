"""Joint-coverage count table: shape, total, and declared-gap emptiness."""

from backend.assumptions.assumptions import FORMATS, PROMO_DEPTH_STEPS, PROMO_MECHANICS
from backend.data.generator import generate
from backend.model.envelope_build import N_PRICE_BINS, build_joint_coverage


def test_counts_shape():
    df = generate(42)
    jc = build_joint_coverage(df)
    assert jc.counts.shape == (
        len(FORMATS),
        len(PROMO_MECHANICS),
        len(PROMO_DEPTH_STEPS),
        N_PRICE_BINS,
    )


def test_counts_sum_equals_row_count():
    df = generate(42)
    jc = build_joint_coverage(df)
    assert int(jc.counts.sum()) == len(df)


def test_no_promo_cells_only_populate_none_mechanic():
    df = generate(42)
    jc = build_joint_coverage(df)
    none_idx = jc.mechanics.index("none")
    depth_zero_idx = jc.depth_steps.index(0)
    # every non-"none" mechanic at depth=0 must be empty (depth=0 implies no promo)
    for m_idx in range(len(jc.mechanics)):
        if m_idx == none_idx:
            continue
        assert jc.counts[:, m_idx, depth_zero_idx, :].sum() == 0
