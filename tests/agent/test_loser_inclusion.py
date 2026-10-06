from __future__ import annotations

from backend.agent.orchestrator import AgentOrchestrator, ScriptedLLM, demo_plan


def test_ac021_goal_board_contains_baseline_and_modeled_loser():
    run = AgentOrchestrator().run("Compare strategies", ScriptedLLM(demo_plan()))
    results = next(event.result for event in run.tool_events if event.name == "evaluate_scenarios")
    baseline_index = next(
        index for index, item in enumerate(run.scenarios)
        if not item.levers and not any(item.cost_shock.model_dump().values())
    )
    baseline_gp = results[baseline_index]["portfolio_gp"]["value"]
    assert any(
        result["status"] != "REFUSED"
        and result["portfolio_gp"]["value"] < baseline_gp
        for result in results
    )
