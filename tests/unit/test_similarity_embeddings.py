"""Deterministic lever/text embeddings for pgvector similarity (no DB required)."""

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.scenario import Lever, Scenario
from backend.similarity import (
    LEVER_DIM,
    TEXT_DIM,
    cosine_distance,
    lever_embedding,
    summarize_run,
    text_embedding,
)


def test_lever_embedding_dim_and_self_distance():
    scenario = Scenario(name="same", levers={SKU_IDS[0]: Lever(price_index=1.05)})
    vec = lever_embedding(scenario)
    assert len(vec) == LEVER_DIM
    assert cosine_distance(vec, lever_embedding(scenario)) < 1e-9


def test_nearby_price_closer_than_far():
    base = Scenario(name="base", levers={SKU_IDS[0]: Lever(price_index=1.00)})
    near = Scenario(name="near", levers={SKU_IDS[0]: Lever(price_index=1.02)})
    far = Scenario(name="far", levers={SKU_IDS[0]: Lever(price_index=1.20)})
    b, n, f = lever_embedding(base), lever_embedding(near), lever_embedding(far)
    assert cosine_distance(b, n) < cosine_distance(b, f)


def test_text_embedding_stable_and_dim():
    a = text_embedding("status=SUPPORTED | focal_gp=12.3")
    b = text_embedding("status=SUPPORTED | focal_gp=12.3")
    assert len(a) == TEXT_DIM
    assert a == b


def test_summarize_refused_has_no_fake_metrics():
    summary = summarize_run(
        {"name": "out", "levers": {}},
        {"refusal_reasons": [{"message": "price outside range"}], "focal": {"gp": {"value": 999}}},
        "REFUSED",
    )
    assert "999" not in summary
    assert "refusal=" in summary
