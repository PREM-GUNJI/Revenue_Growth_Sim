from __future__ import annotations

from backend.agent.auditor import audit_answer
from backend.agent.schemas import AgentAnswer, Claim, ToolEvent


def test_ac020_recommendation_must_reference_modeled_claim():
    event = ToolEvent(call_id="e1", name="evaluate_scenarios", arguments={}, result=[], result_hash="hash")
    answer = AgentAnswer(summary="Recommendation", claims=[
        Claim(claim_id="r1", text="Choose A.", label="Recommended", references=["missing"]),
    ])
    assert any("Recommended claims must reference a Modeled claim" in issue
               for issue in audit_answer(answer, [event]).issues)


def test_ac020_modeled_claim_cannot_use_refused_result():
    event = ToolEvent(
        call_id="e1", name="evaluate_scenarios", arguments={},
        result=[{"status": "REFUSED", "portfolio_gp": None}], result_hash="hash",
    )
    answer = AgentAnswer(summary="No result.", claims=[
        Claim(claim_id="m1", text="No result.", label="Modeled", tool_call_id="e1",
              field_path="0.status"),
    ])
    assert any("Modeled claims cannot cite a refused scenario"
               in issue for issue in audit_answer(answer, [event]).issues)
