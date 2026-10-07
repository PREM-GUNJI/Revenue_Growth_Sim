"""AC-001 (determinism), AC-002 (declared gaps empty), and observed-range checks."""

import subprocess
import sys

import pandas as pd
import pytest

from backend.assumptions.assumptions import PROMO_DEPTH_STEPS, PROMO_MECHANICS
from backend.data.generator import generate, write_dataset

SEED = 42


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return generate(SEED)


def test_same_seed_same_hash_in_process(tmp_path):
    m1 = write_dataset(SEED, tmp_path / "a")
    m2 = write_dataset(SEED, tmp_path / "b")
    assert m1["data_sha256"] == m2["data_sha256"]


def test_same_seed_same_hash_cross_process(tmp_path):
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    for out in (out_a, out_b):
        result = subprocess.run(
            [sys.executable, "-m", "backend.data.generator", str(SEED), str(out)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    hash_a = (out_a / "data_manifest.json").read_text()
    hash_b = (out_b / "data_manifest.json").read_text()
    assert hash_a == hash_b


def test_different_seed_different_hash(tmp_path):
    m1 = write_dataset(SEED, tmp_path / "a")
    m2 = write_dataset(SEED + 1, tmp_path / "b")
    assert m1["data_sha256"] != m2["data_sha256"]


def test_declared_gap_is_empty(df):
    violated = (df["price_index"] > 1.06) & (df["promo_depth_pct"] > 20)
    assert violated.sum() == 0


def test_observed_price_index_range(df):
    assert df["price_index"].min() >= 0.88
    assert df["price_index"].max() <= 1.12


def test_observed_promo_depth_steps(df):
    assert set(df["promo_depth_pct"].unique()) <= set(PROMO_DEPTH_STEPS)


def test_observed_promo_mechanics(df):
    assert set(df["promo_mechanic"].unique()) <= set(PROMO_MECHANICS)


def test_four_pack_formats_only(df):
    assert df["format"].nunique() == 4


def test_all_catalog_skus(df):
    assert df["sku_id"].nunique() == 20  # 5 brands x 4 formats


def test_units_sold_non_negative(df):
    assert (df["units_sold"] >= 0).all()


def test_row_count_matches_dimensions(df):
    # 20 SKUs x 3 regions x 104 weeks x 8 stores
    assert len(df) == 20 * 3 * 104 * 8
