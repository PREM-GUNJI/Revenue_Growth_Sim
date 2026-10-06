"""AC-033: agent + evidence layer. Tools supply every number; research never becomes a recommendation."""

from __future__ import annotations

import inspect

import pytest

from backend.agent.auditor import audit_answer
from backend.agent.orchestrator import AgentOrchestrator, ScriptedLLM, demo_plan, select_research
from backend.agent.schemas import AgentAnswer, Claim, ConjointAlt, ResearchPlan, ToolEvent
from backend.agent.tools import AgentTools, ToolError


def _run(research: ResearchPlan | None):
    plan = demo_plan()
    plan.research = research
    return AgentOrchestrator().run(
        "Improve margin without losing more than 5% volume", ScriptedLLM(plan)
    )


@pytest.mark.parametrize(
    "goal,method",
    [
        ("What is the price ceiling consumers will pay?", "Willingness to Pay"),
        ("Show acceptance at each price point", "Gabor-Granger"),
        (
            "Find the acceptable price range, too cheap and too expensive",
            "Van Westendorp Price Sensitivity Meter",
        ),
        ("Compare brand and pack trade-offs", "Conjoint simulation (supplied utilities)"),
    ],
)
def test_ac033_agent_selects_the_matching_evidence_method(goal, method):
    assert select_research(goal).methodology == method


def test_ac033_agent_skips_research_when_evidence_is_not_relevant():
    assert select_research("Improve margin without losing more than 5% volume") is None


def test_ac033_research_run_is_grounded_labelled_and_recommends_from_engine_results():
    run = _run(ResearchPlan(methodology="Willingness to Pay"))
    names = [e.name for e in run.tool_events]
    for expected in (
        "get_pricing_methodologies",
        "run_wtp",
        "research_to_scenarios",
        "evaluate_scenarios",
    ):
        assert expected in names
    assert run.audit.passed, run.audit.issues
    research_claim = next(c for c in run.answer.claims if c.claim_id == "research-candidate-price")
    event = next(e for e in run.tool_events if e.call_id == research_claim.tool_call_id)
    assert event.name == "run_wtp" and research_claim.research_id == event.result["research_id"]
    engine = {e.call_id: e.name for e in run.tool_events}
    recommended = next(c for c in run.answer.claims if c.label == "Recommended")
    modeled = {c.claim_id: c for c in run.answer.claims if c.label == "Modeled"}
    assert any(
        engine[modeled[ref].tool_call_id] == "evaluate_scenarios" for ref in recommended.references
    )
    assert any("synthetic" in c.lower() for c in run.answer.caveats)


def test_ac033_research_candidates_enter_the_same_board_as_baseline_and_loser():
    run = _run(ResearchPlan(methodology="Gabor-Granger"))
    evaluated = next(e for e in run.tool_events if e.name == "evaluate_scenarios").result
    assert any(not s.levers for s in run.scenarios)  # baseline
    assert len(evaluated) > len(demo_plan().scenarios)
    assert any(
        item["status"] == "REFUSED" for item in evaluated
    )  # demo plan keeps its refused request


def test_ac033_refused_research_candidate_is_not_bypassed():
    refused = ConjointAlt(brand="Aurora", pack="pet_500ml", price=80, promotion="None")
    run = _run(
        ResearchPlan(
            methodology="Conjoint simulation (supplied utilities)",
            alternatives=[refused, ConjointAlt(brand="Aurora", pack="pet_500ml", price=45)],
        )
    )
    evaluated = next(e for e in run.tool_events if e.name == "evaluate_scenarios").result
    eval_event = next(e for e in run.tool_events if e.name == "evaluate_scenarios")
    refused_rows = [i for i, item in enumerate(eval_event.result) if item["status"] == "REFUSED"]
    assert run.audit.passed and refused_rows
    for claim in run.answer.claims:
        if claim.label == "Modeled" and claim.tool_call_id == eval_event.call_id:
            assert int(claim.field_path.split(".")[0]) not in refused_rows
    assert all(item["portfolio_gp"] is None for item in evaluated if item["status"] == "REFUSED")


def test_ac033_agent_cannot_supply_utilities_or_wtp():
    assert "utilities" not in inspect.signature(AgentTools._tool_run_conjoint_simulation).parameters
    tools = AgentTools()
    with pytest.raises(TypeError):
        tools.invoke("run_conjoint_simulation", {"utilities": {"brand": {"Aurora": 9}}})
    with pytest.raises(ToolError):
        tools.invoke("run_unknown_method", {})
    assert "respondents" not in tools.invoke("get_consumer_evidence", {})[1]  # summary only, never every row


def test_ac033_research_alone_cannot_back_a_recommendation():
    research = ToolEvent(
        call_id="r1",
        name="run_wtp",
        arguments={},
        result={"research_id": "RES-X", "candidates": [{"price": 43.0}]},
        result_hash="h",
    )
    answer = AgentAnswer(
        summary="x",
        claims=[
            Claim(
                claim_id="m1",
                text="Candidate is 43.0.",
                label="Modeled",
                tool_call_id="r1",
                field_path="candidates.0.price",
                research_id="RES-X",
            ),
            Claim(claim_id="r", text="Choose it.", label="Recommended", references=["m1"]),
        ],
    )
    assert any(
        "cannot rest on research evidence alone" in i
        for i in audit_answer(answer, [research]).issues
    )


def test_ac033_research_derived_modeled_claims_must_carry_the_research_id():
    research = ToolEvent(
        call_id="r1",
        name="run_wtp",
        arguments={},
        result={"research_id": "RES-X", "candidates": [{"price": 43.0}]},
        result_hash="h",
    )
    answer = AgentAnswer(
        summary="x",
        claims=[
            Claim(
                claim_id="m1",
                text="Candidate is 43.0.",
                label="Modeled",
                tool_call_id="r1",
                field_path="candidates.0.price",
            )
        ],
    )
    assert any("research_id" in i for i in audit_answer(answer, [research]).issues)


def test_ac033_invented_research_numbers_fail_grounding():
    research = ToolEvent(
        call_id="r1",
        name="run_wtp",
        arguments={},
        result={"research_id": "RES-X", "candidates": [{"price": 43.0}]},
        result_hash="h",
    )
    verdict = audit_answer(AgentAnswer(summary="WTP is 61.0 for most buyers."), [research])
    assert not verdict.passed and any("61.0" in i for i in verdict.issues)
