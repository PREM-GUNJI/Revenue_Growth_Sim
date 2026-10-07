"""Programmatic grounding check for numeric text in an agent answer."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from backend.agent.schemas import AgentAnswer, ToolEvent
from backend.assumptions.assumptions import FORMATS, PACK_SIZE_L

_NUMBER = re.compile(r"(?<![\w-])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")


def _pack_label_pattern() -> re.Pattern[str]:
    """Pack names as people write them ("500ml", "500 ml", "1.5 L", "6 x 330ml"), built from the registry's formats.

    These are product labels, not claims about results, so they must not be checked as numbers. Only sizes
    the registry actually defines are exempt: an invented "700ml" is still an ungrounded number.
    """
    forms: list[str] = []
    for format_id in FORMATS:
        match = re.search(r"(?:(\d+)x)?(\d+)ml$", format_id)
        if match is None:
            continue
        count, size = match.group(1), match.group(2)
        forms.append(rf"{count}\s*[x×]\s*{size}\s*ml" if count else rf"{size}\s*ml")
        litres = PACK_SIZE_L.get(format_id)
        if litres is not None and not count:
            forms.append(rf"{re.escape(format(litres, 'g'))}\s*(?:l|litres?|liters?)")
    return re.compile(r"(?<![\w.])(?:" + "|".join(forms) + r")(?!\w)", re.IGNORECASE)


_PACK_LABEL = _pack_label_pattern()


def _rounded(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "").rstrip("%")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    except InvalidOperation:
        return None


def _evidence_numbers(value: Any, key: str = "") -> list[Decimal]:
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float, Decimal)):
        item = _rounded(str(value))
        if item is None:
            return []
        # Prose may round to whole units (₹30,898 for 30,897.7); that is rounding, not a new number.
        return [item, item.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.1"))]
    if isinstance(value, str):
        if key == "result_hash" or re.fullmatch(r"[0-9a-f]{32,}", value):
            return []
        if "reason" in key or "message" in key or re.fullmatch(r"[+-]?\d[\d,.]*%?", value.strip()):
            return [
                number
                for token in _NUMBER.findall(value)
                if (number := _rounded(token)) is not None
            ]
        return []
    if isinstance(value, dict):
        return [
            number
            for name, child in value.items()
            for number in _evidence_numbers(child, str(name))
        ]
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
        for token in _NUMBER.findall(_PACK_LABEL.sub(" ", text)):
            number = _rounded(token)
            if number is None:
                continue
            checked += 1
            if number not in available:
                issues.append("Ungrounded number in answer: " + token)
    return sorted(set(issues)), checked
