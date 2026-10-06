from __future__ import annotations

import pytest

from backend.agent.grounding import check_numeric_grounding
from backend.agent.schemas import AgentAnswer, Claim, ToolEvent


def event(result: object) -> ToolEvent:
    return ToolEvent(call_id="eval-1", name="evaluate_scenarios", arguments={}, result=result, result_hash="hash")


def test_ac017_grounded_number_passes_and_unmatched_number_fails():
    tool = event([{"status": "SUPPORTED", "portfolio_gp": {"value": 1250.04}}])
    grounded = AgentAnswer(summary="Modeled GP is 1,250.0.")
    ungrounded = AgentAnswer(summary="Modeled GP is 1,300.0.")
    assert check_numeric_grounding(grounded, [tool]) == ([], 1)
    issues, checked = check_numeric_grounding(ungrounded, [tool])
    assert checked == 1
    assert issues == ["Ungrounded number in answer: 1,300.0"]


def test_ac018_refusal_text_with_ballpark_number_is_not_grounded():
    tool = event([{
        "status": "REFUSED",
        "refusal_reasons": [{"message": "price_index 1.5 is outside the supported range"}],
    }])
    answer = AgentAnswer(
        summary="Could be around 40% higher.",
        refusals=["price_index 1.5 is outside the supported range"],
    )
    issues, _ = check_numeric_grounding(answer, [tool])
    assert any("40%" in issue for issue in issues)
