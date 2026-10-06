"""Minimal FastAPI app (Phase 3 adds `/assumptions`; Phase 6 adds the rest).

`GET /assumptions` lists the full catalog for inspection/UI display — it
reads `ASSUMPTIONS` directly rather than through `registry.get()`, since
listing every id isn't a computation that should count toward coverage
(see `tests/assumptions/test_registry.py`'s pending-Phase-4 exclusion set).
"""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from backend.agent.openai_llm import OpenAILLM, OpenAILLMError
from backend.agent.orchestrator import AgentOrchestrator
from backend.api.schemas import (
    AgentRunIn,
    AssumptionOut,
    ConjointIn,
    ConjointToScenariosIn,
    ConsumerEvidenceIn,
    EvaluateIn,
    ExportIn,
    ImportIn,
    ResearchIn,
    ResearchToScenariosIn,
    ScenarioIn,
    SweepIn,
)
from backend.assumptions.assumptions import ASSUMPTIONS, SKUS
from backend.db import database_status, list_runs, save_run
from backend.engine.batch import ENGINE_VERSION, _data_hash, _support_envelope, evaluate_batch
from backend.engine.ids import expand_scenario, scenario_id
from backend.engine.scenario import Lever, Scenario
from backend.engine.support import nearest_supported
from backend.model.backtest import spec_hash
from backend.model.spec import build_param_draws
from backend.research.evidence import (CONJOINT_STATEMENT, LABEL, conjoint_defaults, conjoint_simulation,
                                      generate_consumers, research_to_scenarios, run_research,
                                      summarize_consumers)

app = FastAPI(title="Revenue Growth Scenario Simulator")
API_EXPORT_VERSION = 1


@app.get("/pricing/methodologies")
async def pricing_methodologies() -> dict:
    return {"priority_1": ["Willingness to Pay", "Gabor-Granger",
                           "Van Westendorp Price Sensitivity Meter"],
            "priority_2": ["Conjoint simulation"], "optional": ["BPTO", "Price Ladder"]}


@app.post("/pricing/consumer-evidence")
async def consumer_evidence(request: ConsumerEvidenceIn) -> dict:
    return generate_consumers(request.seed, request.sample_size)


@app.post("/pricing/consumer-summary")
async def consumer_summary(request: ConsumerEvidenceIn) -> dict:
    return summarize_consumers(generate_consumers(request.seed, request.sample_size))


@app.post("/pricing/research")
async def pricing_research(request: ResearchIn) -> dict:
    evidence = generate_consumers(request.seed, request.sample_size)
    result = run_research(request.methodology, evidence, request.prices or None, request.pack)
    return {**asdict(result), "label": LABEL}


@app.get("/pricing/conjoint/defaults")
async def pricing_conjoint_defaults() -> dict:
    return conjoint_defaults()


@app.post("/pricing/conjoint")
async def pricing_conjoint(request: ConjointIn) -> dict:
    try:
        result = conjoint_simulation(generate_consumers(request.seed, request.sample_size),
                                     request.alternatives, request.utilities, request.focus_brand)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**asdict(result), "label": LABEL, "statement": CONJOINT_STATEMENT}


@app.post("/pricing/research-to-scenarios")
async def research_candidates(request: ResearchToScenariosIn) -> dict:
    evidence = generate_consumers(request.seed, request.sample_size)
    result = run_research(request.methodology, evidence, request.prices or None, request.pack)
    return {"research": asdict(result), "label": LABEL, "scenarios": research_to_scenarios(
        result, request.brand, request.promotion_depth_pct)}


@app.post("/pricing/conjoint-to-scenarios")
async def conjoint_candidates(request: ConjointToScenariosIn) -> dict:
    try:
        result = conjoint_simulation(generate_consumers(request.seed, request.sample_size),
                                     request.alternatives, request.utilities, request.focus_brand)
        scenarios = research_to_scenarios(result, request.focus_brand)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"research": {**asdict(result), "statement": CONJOINT_STATEMENT}, "label": LABEL, "scenarios": scenarios}


@app.get("/assumptions", response_model=list[AssumptionOut])
async def list_assumptions() -> list[AssumptionOut]:
    return [
        AssumptionOut(
            id=a.id,
            label=a.label,
            value=a.value,
            unit=a.unit,
            source=a.source,
            rationale=a.rationale,
            valid_range=a.valid_range,
        )
        for a in sorted(ASSUMPTIONS.values(), key=lambda a: a.id)
    ]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Verify the deterministic engine assets needed to serve scenarios."""
    try:
        _support_envelope()
        _data_hash()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="engine assets are unavailable") from exc
    return {"status": "ready", "engine_version": ENGINE_VERSION}


@app.get("/database/health")
async def database_health() -> dict[str, str]:
    return {"status": database_status()}


@app.post("/scenario-runs")
async def create_scenario_run(request: ExportIn) -> dict:
    result = asdict(
        evaluate_batch([request.scenario], build_param_draws(k=request.k, seed=request.seed))[0]
    )
    record = {
        "id": str(uuid4()),
        "scenario_id": result["scenario_id"],
        "status": result["status"],
        "result_hash": result["result_hash"],
        "k": request.k,
        "seed": request.seed,
        "scenario": request.scenario.model_dump(mode="json"),
        "result": jsonable_encoder(result),
    }
    try:
        save_run(record)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="PostgreSQL is unavailable or not configured"
        ) from exc
    return {**record, "created_at": None}


@app.get("/scenario-runs")
async def get_scenario_runs(limit: int = 100) -> list[dict]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    try:
        rows = list_runs(limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="PostgreSQL is unavailable or not configured"
        ) from exc
    return [
        {
            "id": row.id, "scenario_id": row.scenario_id, "status": row.status,
            "result_hash": row.result_hash, "k": row.k, "seed": row.seed,
            "scenario": row.scenario, "result": row.result, "created_at": row.created_at,
        }
        for row in rows
    ]


@app.post("/agent/run")
def run_agent(request: AgentRunIn) -> dict:
    import os
    from pathlib import Path
    from uuid import uuid4

    if os.getenv("LLM_PROVIDER", "openai").lower() != "openai":
        raise HTTPException(status_code=503, detail="This build is configured for the OpenAI provider")
    trace_id = uuid4().hex
    trace_path = Path(os.getenv("AGENT_TRACE_DIR", "data/traces")) / (trace_id + ".jsonl")
    try:
        run = AgentOrchestrator().run(request.goal, OpenAILLM(), trace_path=trace_path)
    except OpenAILLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"trace_id": trace_id, **run.model_dump(mode="json")}


@app.get("/model/info")
async def model_info() -> dict:
    return {"engine_version": ENGINE_VERSION, "model_spec_hash": spec_hash(),
            "data_hash": _data_hash(), "sku_count": len(SKUS),
            "assumption_count": len(ASSUMPTIONS), "deterministic": True}


@app.get("/envelope")
async def envelope_info() -> dict:
    env = _support_envelope()
    return {"price_index_p1_p99": env.baselines.price_index_p1_p99,
            "promo_depth_observed": env.baselines.promo_depth_observed,
            "formats": env.coverage.formats, "mechanics": env.coverage.mechanics,
            "depth_steps": env.coverage.depth_steps,
            "price_bin_edges": env.coverage.price_bin_edges.tolist(),
            "joint_coverage_counts": env.coverage.counts.tolist(),
            "minimum_local_rows": ASSUMPTIONS["A-022"].value,
            "comfortable_local_rows": ASSUMPTIONS["A-023"].value}


@app.post("/scenarios/evaluate")
async def evaluate(request: EvaluateIn) -> list[dict]:
    draws = build_param_draws(k=request.k, seed=request.seed)
    return jsonable_encoder([asdict(x) for x in evaluate_batch(request.scenarios, draws)])


@app.post("/scenarios/nearest_supported")
async def nearest(request: ScenarioIn) -> dict:
    env = _support_envelope()
    suggestion = nearest_supported(request.scenario, env)
    decision = env.check(suggestion.scenario)
    if decision.status == "REFUSED":
        raise HTTPException(status_code=500, detail="nearest-supported invariant failed")
    return {"scenario": suggestion.scenario.model_dump(mode="json"),
            "scenario_id": scenario_id(expand_scenario(suggestion.scenario)),
            "distance": suggestion.distance, "status": decision.status}


@app.post("/scenarios/sweep")
async def sweep(request: SweepIn) -> list[dict]:
    if request.sku_id not in {item["sku_id"] for item in SKUS}:
        raise HTTPException(status_code=422, detail="unknown sku_id")
    default = request.scenario.levers.get(request.sku_id, Lever())
    mechanic = "TPR" if request.lever == "promo_depth_pct" and default.mechanic == "none" else default.mechanic
    scenarios = []
    for value in request.values:
        source = request.scenario.model_copy(deep=True)
        prior = source.levers.get(request.sku_id, Lever())
        changes = {request.lever: value}
        if request.lever == "promo_depth_pct":
            changes["mechanic"] = "none" if value == 0 else mechanic
            if value == 0:
                changes["promo_weeks_per_month"] = 0.0
        source.levers[request.sku_id] = prior.model_copy(update=changes)
        scenarios.append(source)
    draws = build_param_draws(k=request.k, seed=request.seed)
    return jsonable_encoder([asdict(x) for x in evaluate_batch(scenarios, draws)])


def _export_payload(scenario: Scenario, k: int, seed: int) -> dict:
    result = evaluate_batch([scenario], build_param_draws(k=k, seed=seed))[0]
    return {"export_version": API_EXPORT_VERSION, "scenario": scenario.model_dump(mode="json"),
            "scenario_id": result.scenario_id, "result_hash": result.result_hash,
            "status": result.status, "k": k, "seed": seed}


@app.post("/scenarios/export")
async def export_scenario(request: ExportIn) -> dict:
    return _export_payload(request.scenario, request.k, request.seed)


@app.post("/scenarios/import")
async def import_scenario(request: ImportIn) -> dict:
    if request.export_version != API_EXPORT_VERSION:
        raise HTTPException(status_code=422, detail="unsupported export version")
    actual_id = scenario_id(expand_scenario(request.scenario))
    if actual_id != request.scenario_id:
        raise HTTPException(status_code=422, detail="scenario_id does not match scenario payload")
    actual = _export_payload(request.scenario, request.k, request.seed)
    if actual["result_hash"] != request.result_hash:
        raise HTTPException(status_code=422, detail="result_hash does not match recomputed result")
    return actual
