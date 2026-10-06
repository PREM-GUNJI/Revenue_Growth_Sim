"""Pydantic response models for the API (Phase 3 adds one; Phase 6 adds the rest)."""

from __future__ import annotations

from pydantic import BaseModel


class AssumptionOut(BaseModel):
    id: str
    label: str
    value: object
    unit: str | None
    source: str
    rationale: str
    valid_range: tuple[float, float] | None = None
