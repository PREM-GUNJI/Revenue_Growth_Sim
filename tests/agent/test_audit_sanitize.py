"""Sanitizer repairs common live-LLM auditor failures before scoring."""

from __future__ import annotations

from backend.agent.auditor import audit_answer, sanitize_answer_for_audit
from backend.agent.schemas import AgentAnswer, Claim, ToolEvent


def test_sanitize_injects_verbatim_refusal_and_drops_bad_observed_claim():
    refusal = "Aurora-can_330ml: price_index 0.9 outside observed 1st-99th percentile [0.9424, 1.1082]"
    events = [
        ToolEvent(
            call_id="eval-1",
            name="evaluate_scenarios",
            arguments={},
            result=[{"status": "REFUSED", "refusal_reasons": [{"message": refusal}]}],
            result_hash="hash",
        )
    ]
    draft = AgentAnswer(
        summary="No estimate.",
        refusals=["The cut was outside the historical range."],
        claims=[
            Claim(
                claim_id="C-obs",
                text="The engine refused the cut.",
                label="Observed",
                tool_call_id="eval-1",
                field_path="0.refusal_reasons",
            )
        ],
    )
    cleaned = sanitize_answer_for_audit(draft, events)
    assert refusal in cleaned.refusals
    assert cleaned.claims == []
    assert audit_answer(cleaned, events).passed


def test_sanitize_drops_assumed_claim_that_does_not_cite_registry():
    events = [
        ToolEvent(
            call_id="eval-1",
            name="evaluate_scenarios",
            arguments={},
            result=[{"status": "SUPPORTED", "focal": {"gp": {"value": 100.0}}, "assumption_ids": ["A-001"]}],
            result_hash="hash",
        )
    ]
    draft = AgentAnswer(
        summary="GP is 100.0.",
        claims=[
            Claim(
                claim_id="C-m",
                text="GP is 100.0.",
                label="Modeled",
                tool_call_id="eval-1",
                field_path="0.focal.gp.value",
            ),
            Claim(
                claim_id="C-a",
                text="This rests on shared elasticities.",
                label="Assumed",
                tool_call_id="eval-1",
                field_path="0.assumption_ids",
            ),
            Claim(
                claim_id="C-r",
                text="Prefer the option.",
                label="Recommended",
                references=["C-m", "C-a"],
            ),
        ],
    )
    cleaned = sanitize_answer_for_audit(draft, events)
    assert [claim.claim_id for claim in cleaned.claims] == ["C-m", "C-r"]
    assert cleaned.claims[1].references == ["C-m"]
    assert audit_answer(cleaned, events).passed
