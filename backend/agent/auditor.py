"""Auditor entry point: grounding, label rules, and refusal integrity."""

from __future__ import annotations

from typing import Any

from backend.agent.grounding import check_numeric_grounding
from backend.agent.labels import validate_claim_labels
from backend.agent.schemas import AgentAnswer, AuditVerdict, ToolEvent

_OBSERVED_TOOLS = frozenset({
    "get_envelope", "get_assumptions", "get_model_info", "find_similar_runs",
})


def _refusal_messages(value: Any) -> list[str]:
    if isinstance(value, dict):
        messages = []
        if value.get("status") == "REFUSED":
            messages.extend(
                item.get("message", "") if isinstance(item, dict) else str(item)
                for item in value.get("refusal_reasons", [])
            )
        for child in value.values():
            messages.extend(_refusal_messages(child))
        return messages
    if isinstance(value, list):
        return [message for child in value for message in _refusal_messages(child)]
    return []


def sanitize_answer_for_audit(answer: AgentAnswer, events: list[ToolEvent]) -> AgentAnswer:
    """Deterministic repairs for common live-LLM slips before the Auditor scores the answer.

    Does not invent commercial numbers. Ensures refusal text is verbatim from tool results and
    drops claims that use the wrong label/source (those belong in refusals or caveats, not claims).
    """
    by_id = {event.call_id: event for event in events}
    required = [message for event in events for message in _refusal_messages(event.result) if message]
    refusals = list(answer.refusals)
    for message in required:
        if message not in refusals:
            refusals.append(message)

    kept = []
    for claim in answer.claims:
        source = by_id.get(claim.tool_call_id or "")
        if claim.label == "Observed" and (source is None or source.name not in _OBSERVED_TOOLS):
            continue
        if claim.label == "Assumed" and (source is None or source.name != "get_assumptions"):
            continue
        kept.append(claim)

    kept_ids = {claim.claim_id for claim in kept}
    fixed = []
    for claim in kept:
        if claim.label != "Recommended":
            fixed.append(claim)
            continue
        refs = [ref for ref in claim.references if ref in kept_ids]
        if not refs:
            continue
        fixed.append(claim.model_copy(update={"references": refs}) if refs != claim.references else claim)

    return answer.model_copy(update={"refusals": refusals, "claims": fixed})


def audit_answer(answer: AgentAnswer, events: list[ToolEvent]) -> AuditVerdict:
    issues = validate_claim_labels(answer, events)
    number_issues, checked = check_numeric_grounding(answer, events)
    issues.extend(number_issues)
    required_refusals = [message for event in events for message in _refusal_messages(event.result)]
    for message in required_refusals:
        if message and message not in answer.refusals:
            issues.append("A refusal reason was omitted or altered")
    return AuditVerdict(passed=not issues, issues=sorted(set(issues)), numbers_checked=checked)
