"""Regenerate synthetic scanner data for every registered market pack."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.data.generator import write_dataset
from backend.markets.packs import list_markets

ROOT = Path(__file__).resolve().parents[2]
MARKETS_DIR = ROOT / "data" / "markets"
SEED = 42


def generate_all(seed: int = SEED) -> list[dict]:
    MARKETS_DIR.mkdir(parents=True, exist_ok=True)
    manifests = []
    for market in list_markets():
        out = MARKETS_DIR / market.id
        manifest = write_dataset(seed, out, market=market)
        manifests.append(manifest)
        print(json.dumps(manifest, indent=2))
        # Keep root data/ as the India pack for older tooling and docs.
        if market.id == "in":
            root = ROOT / "data"
            root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out / "data.parquet", root / "data.parquet")
            shutil.copy2(out / "data_manifest.json", root / "data_manifest.json")
    return manifests


if __name__ == "__main__":
    generate_all()
