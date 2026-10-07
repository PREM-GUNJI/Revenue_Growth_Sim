from backend.agent.orchestrator import AgentOrchestrator, ScriptedLLM, _volume_cap, demo_plan
from backend.analysis import goal_seek, sensitivity
from backend.engine.scenario import Lever, Scenario


def test_refused_scenario_gets_engine_evaluated_alternative():
    run = AgentOrchestrator().run("compare", ScriptedLLM(demo_plan()))
    assert run.alternatives, "refused scenario must get a nearest-supported alternative"
    alt = run.alternatives[0]
    assert alt["result"]["status"] != "REFUSED" and alt["result"]["portfolio_gp"] is not None
    assert run.scenarios[alt["refused_index"]].name == "Out-of-range price request"


def test_goal_seek_respects_volume_cap_and_is_deterministic():
    a, b = goal_seek(5.0, top=3), goal_seek(5.0, top=3)
    assert a == b and a["top"]
    assert all(r["volume_loss_pct"] <= 5.0 and r["gp_change"] > 0 for r in a["top"])


def test_sensitivity_ranks_assumptions_and_skips_refused():
    refused = Scenario(name="x", levers={"Aurora-can_330ml": Lever(price_index=1.5)})
    out = sensitivity([Scenario(name="b"), Scenario(name="p", levers={"Aurora-can_330ml": Lever(price_index=1.04)}), refused])
    assert 2 not in out["base_ranking"] and out["assumptions"][0]["swing"] >= out["assumptions"][-1]["swing"]


def test_volume_cap_parsed_from_goal():
    assert _volume_cap("Improve margin without losing more than 5% volume.") == 5.0
    assert _volume_cap("What price would consumers accept?") is None
