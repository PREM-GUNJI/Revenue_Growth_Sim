"""Validation rules for the four agent claim labels."""

from __future__ import annotations

from typing import Any

from backend.agent.schemas import AgentAnswer, ToolEvent


def _field(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def validate_claim_labels(answer: AgentAnswer, events: list[ToolEvent]) -> list[str]:
    by_id = {event.call_id: event for event in events}
    modeled_ids = {claim.claim_id for claim in answer.claims if claim.label == "Modeled"}
    issues = []
    modeled_tools = {"evaluate_scenarios", "sweep", "explain_scenario", "calc"}

    for claim in answer.claims:
        source = by_id.get(claim.tool_call_id or "")
        if claim.label in {"Modeled", "Observed", "Assumed"} and source is None:
            issues.append(f"{claim.claim_id}: {claim.label} claims need a source tool call")
            continue
        if claim.label == "Modeled":
            if source.name not in modeled_tools or not claim.field_path:
                issues.append(f"{claim.claim_id}: Modeled claims need a numeric result field from a modeling tool")
                continue
            try:
                value = _field(source.result, claim.field_path)
                if value is None or isinstance(value, (dict, list)):
                    issues.append(f"{claim.claim_id}: Modeled claim points to an empty or non-scalar result")
                parts = claim.field_path.split(".")
                if source.name in {"evaluate_scenarios", "sweep"}:
                    row = _field(source.result, parts[0])
                    if row.get("status") == "REFUSED":
                        issues.append(f"{claim.claim_id}: Modeled claims cannot cite a refused scenario")
                elif source.name == "explain_scenario" and source.result.get("status") == "REFUSED":
                    issues.append(f"{claim.claim_id}: Modeled claims cannot cite a refused scenario")
            except (KeyError, IndexError, ValueError, TypeError, AttributeError):
                issues.append(f"{claim.claim_id}: field path does not exist in its tool result")
        elif claim.label == "Observed" and source.name not in {"get_envelope", "get_assumptions", "get_model_info"}:
            issues.append(f"{claim.claim_id}: Observed claims must cite observed or registry data")
        elif claim.label == "Assumed" and source.name != "get_assumptions":
            issues.append(f"{claim.claim_id}: Assumed claims must cite the assumptions registry")
        elif claim.label == "Recommended" and not (set(claim.references) & modeled_ids):
            issues.append(f"{claim.claim_id}: Recommended claims must reference a Modeled claim")
    return sorted(set(issues))
