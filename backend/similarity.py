"""Deterministic embeddings for historical run similarity (pgvector).

Lever vectors are quantized scenario features — not fitted, not neural.
Text vectors are a fixed bag-of-hashes over a compact summary string.
Neither path replaces nearest_supported or softens REFUSED.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from backend.assumptions.assumptions import N_SKUS, PROMO_MECHANICS, SKU_IDS
from backend.engine.ids import expand_scenario
from backend.engine.scenario import Scenario
from backend.markets.context import get_active_market_id

LEVER_DIM = N_SKUS * (3 + len(PROMO_MECHANICS)) + 3  # price, depth, weeks, mech one-hot, + cost shock
TEXT_DIM = 384
_TOKEN = re.compile(r"[a-z0-9%._-]+", re.IGNORECASE)


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def lever_embedding(scenario: Scenario | dict[str, Any]) -> list[float]:
    """Fixed-dim feature vector from quantized levers + cost shock."""
    model = Scenario.model_validate(scenario) if isinstance(scenario, dict) else scenario
    expanded = expand_scenario(model)
    feats: list[float] = []
    for sku in SKU_IDS:
        lv = expanded.levers[sku]
        feats.append(lv.price_bp / 1000.0)
        feats.append(lv.depth_pct / 100.0)
        feats.append(lv.weeks_per_month / 4.0)
        for mechanic in PROMO_MECHANICS:
            feats.append(1.0 if lv.mechanic == mechanic else 0.0)
    feats.append(expanded.cost_shock["aluminium_pct"] / 1000.0)
    feats.append(expanded.cost_shock["pet_resin_pct"] / 1000.0)
    feats.append(expanded.cost_shock["sugar_pct"] / 1000.0)
    if len(feats) != LEVER_DIM:
        raise RuntimeError(f"lever embedding dim {len(feats)} != {LEVER_DIM}")
    return _l2_normalize(feats)


def text_embedding(text: str) -> list[float]:
    """Deterministic bag-of-hashes embedding (no external model)."""
    vec = [0.0] * TEXT_DIM
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % TEXT_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    return _l2_normalize(vec)


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity for L2-normalized vectors."""
    if len(a) != len(b):
        raise ValueError("embedding lengths must match")
    return 1.0 - sum(x * y for x, y in zip(a, b, strict=True))


def summarize_run(
    scenario: dict[str, Any],
    result: dict[str, Any] | None,
    status: str,
) -> str:
    """Compact text for display and text_embedding. No refused numeric outputs."""
    name = scenario.get("name") or "unnamed"
    parts = [f"status={status}", f"name={name}"]
    if status == "REFUSED":
        reasons = (result or {}).get("refusal_reasons") or []
        messages = [r.get("message", "") for r in reasons if isinstance(r, dict)]
        parts.append("refusal=" + "; ".join(m for m in messages if m)[:400])
    elif result:
        focal = result.get("focal") or {}
        gp = (focal.get("gp") or {}).get("value")
        vol = (focal.get("volume") or {}).get("value")
        if gp is not None:
            parts.append(f"focal_gp={gp:.4g}")
        if vol is not None:
            parts.append(f"focal_volume={vol:.4g}")
    levers = scenario.get("levers") or {}
    for sku in SKU_IDS[:4]:
        lv = levers.get(sku) or {}
        if lv:
            parts.append(
                f"{sku}:pi={lv.get('price_index', 1)}:d={lv.get('promo_depth_pct', 0)}"
                f":m={lv.get('mechanic', 'none')}"
            )
    return " | ".join(parts)[:1500]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def upsert_run_embedding(
    *,
    run_id: str,
    scenario_id: str,
    status: str,
    scenario: dict[str, Any],
    result: dict[str, Any] | None,
    workspace_id: str | None = None,
    market_id: str | None = None,
) -> None:
    """Write/replace the embedding row for a persisted scenario run."""
    from backend.db import get_session_factory, initialize_database

    factory = get_session_factory()
    if factory is None:
        return
    initialize_database()
    summary = summarize_run(scenario, result, status)
    lever_lit = _vector_literal(lever_embedding(scenario))
    text_lit = _vector_literal(text_embedding(summary))
    mid = market_id or get_active_market_id()
    now = datetime.now(UTC)
    sql = """
    INSERT INTO run_embeddings (
        run_id, scenario_id, workspace_id, status, market_id, created_at,
        lever_embedding, text_embedding, summary_text
    ) VALUES (
        :run_id, :scenario_id, :workspace_id, :status, :market_id, :created_at,
        CAST(:lever AS vector), CAST(:text_vec AS vector), :summary
    )
    ON CONFLICT (run_id) DO UPDATE SET
        scenario_id = EXCLUDED.scenario_id,
        workspace_id = EXCLUDED.workspace_id,
        status = EXCLUDED.status,
        market_id = EXCLUDED.market_id,
        lever_embedding = EXCLUDED.lever_embedding,
        text_embedding = EXCLUDED.text_embedding,
        summary_text = EXCLUDED.summary_text
    """
    with factory() as session:
        session.execute(
            text(sql),
            {
                "run_id": run_id,
                "scenario_id": scenario_id,
                "workspace_id": workspace_id,
                "status": status,
                "market_id": mid,
                "created_at": now,
                "lever": lever_lit,
                "text_vec": text_lit,
                "summary": summary,
            },
        )
        session.commit()


def find_similar_runs(
    *,
    scenario: Scenario | dict[str, Any] | None = None,
    query_text: str | None = None,
    limit: int = 10,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    """Rank past runs by lever and/or text cosine distance via pgvector."""
    from backend.db import get_session_factory, initialize_database

    if scenario is None and not (query_text and query_text.strip()):
        raise ValueError("provide scenario and/or query_text")
    limit = max(1, min(int(limit), 50))
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    initialize_database()

    order_parts: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    where = ["1=1"]
    if workspace_id:
        where.append("workspace_id = :workspace_id")
        params["workspace_id"] = workspace_id

    select_distance = "0.0::float8 AS distance"
    if scenario is not None and query_text and query_text.strip():
        params["lever"] = _vector_literal(lever_embedding(scenario))
        params["text"] = _vector_literal(text_embedding(query_text))
        select_distance = (
            "(0.5 * (lever_embedding <=> CAST(:lever AS vector)) "
            "+ 0.5 * (text_embedding <=> CAST(:text AS vector))) AS distance"
        )
        order_parts.append("distance")
    elif scenario is not None:
        params["lever"] = _vector_literal(lever_embedding(scenario))
        select_distance = "(lever_embedding <=> CAST(:lever AS vector)) AS distance"
        order_parts.append("distance")
    else:
        params["text"] = _vector_literal(text_embedding(query_text or ""))
        select_distance = "(text_embedding <=> CAST(:text AS vector)) AS distance"
        order_parts.append("distance")

    sql = f"""
    SELECT run_id, scenario_id, workspace_id, status, market_id, created_at,
           summary_text, {select_distance}
    FROM run_embeddings
    WHERE {" AND ".join(where)}
    ORDER BY {", ".join(order_parts)}, created_at DESC
    LIMIT :limit
    """
    with factory() as session:
        rows = session.execute(text(sql), params).mappings().all()
    return [
        {
            "run_id": row["run_id"],
            "scenario_id": row["scenario_id"],
            "workspace_id": row["workspace_id"],
            "status": row["status"],
            "market_id": row["market_id"],
            "created_at": row["created_at"],
            "summary_text": row["summary_text"],
            "distance": float(row["distance"]),
            "label": "Observed",
            "note": (
                "Prior persisted run. Distances are historical similarity only; "
                "not a substitute for evaluate_scenarios or nearest_supported."
            ),
        }
        for row in rows
    ]
