"""Programmatic grounding check for numeric text in an agent answer."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from backend.agent.schemas import AgentAnswer, ToolEvent

_NUMBER = re.compile(r"(?<![\w-])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")


def _rounded(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "").rstrip("%")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _evidence_numbers(value: Any, key: str = "") -> list[Decimal]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float, Decimal)):
        item = _rounded(str(value))
        return [item] if item is not None else []
    if isinstance(value, str):
        if key == "result_hash" or re.fullmatch(r"[0-9a-f]{32,}", value):
            return []
        if "reason" in key or "message" in key or re.fullmatch(r"[+-]?\d[\d,.]*%?", value.strip()):
            return [number for token in _NUMBER.findall(value) if (number := _rounded(token)) is not None]
        return []
    if isinstance(value, dict):
        return [number for name, child in value.items() for number in _evidence_numbers(child, str(name))]
    if isinstance(value, (list, tuple)):
        return [number for child in value for number in _evidence_numbers(child, key)]
    return []


def check_numeric_grounding(answer: AgentAnswer, events: list[ToolEvent]) -> tuple[list[str], int]:
    available = [number for event in events for number in _evidence_numbers(event.result)]
    texts = [answer.summary, *answer.recommendations, *answer.refusals, *answer.caveats]
    texts.extend(claim.text for claim in answer.claims)
    issues: list[str] = []
    checked = 0
    for text in texts:
        for token in _NUMBER.findall(text):
            number = _rounded(token)
            if number is None:
                continue
            checked += 1
            if number not in available:
                issues.append("Ungrounded number in answer: " + token)
    return sorted(set(issues)), checked
