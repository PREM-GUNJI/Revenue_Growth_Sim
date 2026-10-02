"""EDA: plots price index vs promo depth so the declared joint-support gap
(GAP-1: price_index > 1.06 together with promo_depth_pct > 20) is visible.

Usage: uv run python -m backend.data.eda [seed]
Writes reports/eda_price_promo_coverage.png (generated, not hand-edited).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backend.data.generator import generate


def plot_coverage(seed: int, out_path: Path) -> None:
    df = generate(seed)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(
        df["price_index"],
        df["promo_depth_pct"],
        s=4,
        alpha=0.08,
        color="tab:blue",
        label="observed (sku, region, week)",
    )
    ax.axvspan(1.06, 1.12, ymin=20 / 30, ymax=1.0, color="red", alpha=0.08)
    ax.annotate(
        "GAP-1: deliberately empty\n(price_index > 1.06 & depth > 20%)",
        xy=(1.09, 25),
        fontsize=9,
        color="firebrick",
    )
    ax.set_xlabel("price_index")
    ax.set_ylabel("promo_depth_pct")
    ax.set_title("Price index vs promo depth coverage (synthetic scanner data)")
    ax.legend(loc="upper left")
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    plot_coverage(seed, Path("reports/eda_price_promo_coverage.png"))
    print("wrote reports/eda_price_promo_coverage.png")
