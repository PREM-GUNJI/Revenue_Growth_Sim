"""AC-017: every number in the agent's final answer matches, after rounding,
a value in that run's tool results or a calc result."""

from __future__ import annotations

from backend.agent.grounding import check_numeric_grounding
from backend.agent.schemas import AgentAnswer, ToolEvent


def event(result: object) -> ToolEvent:
    return ToolEvent(
        call_id="eval-1", name="evaluate_scenarios", arguments={}, result=result, result_hash="hash"
    )


def test_ac017_grounded_number_passes_and_unmatched_number_fails():
    tool = event([{"status": "SUPPORTED", "portfolio_gp": {"value": 1250.04}}])
    grounded = AgentAnswer(summary="Modeled GP is 1,250.0.")
    ungrounded = AgentAnswer(summary="Modeled GP is 1,300.0.")
    assert check_numeric_grounding(grounded, [tool]) == ([], 1)
    issues, checked = check_numeric_grounding(ungrounded, [tool])
    assert checked == 1
    assert issues == ["Ungrounded number in answer: 1,300.0"]


def test_ac018_refusal_text_with_ballpark_number_is_not_grounded():
    tool = event(
        [
            {
                "status": "REFUSED",
                "refusal_reasons": [{"message": "price_index 1.5 is outside the supported range"}],
            }
        ]
    )
    answer = AgentAnswer(
        summary="Could be around 40% higher.",
        refusals=["price_index 1.5 is outside the supported range"],
    )
    issues, _ = check_numeric_grounding(answer, [tool])
    assert any("40%" in issue for issue in issues)



def test_pack_names_are_labels_not_numbers_to_ground():
    """Regression: "500ml PET" made the auditor report 'Ungrounded number in answer: 500'."""
    tool = event([{"status": "SUPPORTED", "portfolio_gp": {"value": 1250.04}}])
    for text in ("Adopt the price for Aurora 500ml PET.", "The 500 ml pack holds up.", "Modeled GP is 1,250.0 on the 330ml can.",
                 "The 1.5 L bottle and the 1.5L bottle.", "Try the 6 x 330ml multipack and the 6x330 ml multipack.",
                 "A 1500ml bottle."):
        assert check_numeric_grounding(AgentAnswer(summary=text), [tool])[0] == [], text


def test_pack_label_exemption_does_not_excuse_other_numbers():
    tool = event([{"status": "SUPPORTED", "portfolio_gp": {"value": 1250.04}}])
    cases = {
        "Adopt 500ml PET with GP of 500.": "500",       # a bare 500 elsewhere in the sentence is still a claim
        "A 700ml pack would sell well.": "700",         # sizes the registry does not define are not exempt
        "Volume rises 12.5% for the 500ml PET.": "12.5%",
        "Profit is 330 on the 330ml can.": "330",
    }
    for text, flagged in cases.items():
        assert check_numeric_grounding(AgentAnswer(summary=text), [tool])[0] == [f"Ungrounded number in answer: {flagged}"], text
