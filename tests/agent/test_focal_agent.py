"""The agent works on the focal brand's profit and sees the baseline before it plans."""

from __future__ import annotations

from backend.agent.orchestrator import AgentOrchestrator, ScriptedLLM, demo_plan
from backend.agent.tools import AgentTools


def run_demo():
    seen: dict = {}

    class Spy(ScriptedLLM):
        def plan(self, goal, context):
            seen.update(context)
            return super().plan(goal, context)

    return AgentOrchestrator().run("Compare strategies", Spy(demo_plan())), seen


def test_planner_context_carries_the_baseline_tool_result() -> None:
    run, seen = run_demo()
    event = next(e for e in run.tool_events if e.name == "get_baseline")
    assert seen["baseline"] == event.result and seen["baseline_tool_call_id"] == event.call_id
    assert seen["baseline"]["focal_brand"] == "Aurora" and len(seen["baseline"]["packs"]) == 4
    assert seen["baseline"]["currency"] == "INR"


def test_baseline_context_is_focal_only_and_engine_labelled() -> None:
    _run, seen = run_demo()
    text = str(seen["baseline"])
    assert "Boreal" in text and "Comet" in text  # only as price gaps, never as rows with their own profit
    assert all(pack["sku_id"].startswith("Aurora-") for pack in seen["baseline"]["packs"])
    assert "deterministic engine" in seen["baseline"]["note"]


def test_ranking_uses_focal_gross_profit_and_never_ranks_a_refused_scenario() -> None:
    run, _ = run_demo()
    evaluated = next(e.result for e in run.tool_events if e.name == "evaluate_scenarios")
    ranking = next(e.result for e in run.tool_events if e.name == "rank_scenarios")
    scores = [row["score"] for row in ranking]
    assert scores == sorted(scores, reverse=True)
    for row in ranking:
        assert evaluated[row["index"]]["status"] != "REFUSED"
        assert row["score"] == evaluated[row["index"]]["focal"]["gp"]["value"]


def test_the_recommendation_cites_the_focal_gross_profit_field() -> None:
    run, _ = run_demo()
    modeled = next(c for c in run.answer.claims if c.claim_id == "modeled-best-gp")
    assert modeled.field_path.endswith(".focal.gp.value") and run.audit.passed


def test_explain_scenario_returns_rupee_bridge_and_assumption_ids() -> None:
    tools = AgentTools()
    scenario = {"name": "up", "levers": {"Aurora-can_330ml": {"price_index": 1.03}}}
    _id, result = tools.invoke("explain_scenario", {"scenario": scenario})
    assert set(result["focal_bridge"]) == {"price", "volume", "cross_pack", "promo", "trade", "cogs", "total"}
    parts = ("price", "volume", "cross_pack", "promo", "trade", "cogs")
    assert abs(sum(result["focal_bridge"][p] for p in parts) - result["focal_bridge"]["total"]) < 0.011
    assert "A-001" in result["assumption_ids"]


def test_rank_tool_still_supports_the_all_brand_metric_when_asked() -> None:
    tools = AgentTools()
    _id, evaluated = tools.invoke("evaluate_scenarios", {"scenarios": [{"name": "a"}, {"name": "b", "levers": {"Aurora-can_330ml": {"price_index": 1.02}}}]})
    _id, ranking = tools.invoke("rank_scenarios", {"results": evaluated, "metric": "portfolio_gp"})
    assert ranking[0]["score"] == max(item["portfolio_gp"]["value"] for item in evaluated)
