"""Auditor entry point: grounding, label rules, and refusal integrity."""

from __future__ import annotations

from typing import Any

from backend.agent.grounding import check_numeric_grounding
from backend.agent.labels import validate_claim_labels
from backend.agent.schemas import AgentAnswer, AuditVerdict, ToolEvent


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


def audit_answer(answer: AgentAnswer, events: list[ToolEvent]) -> AuditVerdict:
    issues = validate_claim_labels(answer, events)
    number_issues, checked = check_numeric_grounding(answer, events)
    issues.extend(number_issues)
    required_refusals = [message for event in events for message in _refusal_messages(event.result)]
    for message in required_refusals:
        if message and message not in answer.refusals:
            issues.append("A refusal reason was omitted or altered")
    return AuditVerdict(passed=not issues, issues=sorted(set(issues)), numbers_checked=checked)
