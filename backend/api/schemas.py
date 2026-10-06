"""Pydantic response models for the API (Phase 3 adds one; Phase 6 adds the rest)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.scenario import Scenario


class AssumptionOut(BaseModel):
    id: str
    label: str
    value: object
    unit: str | None
    source: str
    rationale: str
    valid_range: tuple[float, float] | None = None


class EvaluateIn(BaseModel):
    scenarios: list[Scenario] = Field(min_length=1, max_length=10_000)
    k: int = Field(default=200, ge=0, le=2_000)
    seed: int = Field(default=42, ge=0)


class ScenarioIn(BaseModel):
    scenario: Scenario


class ExportIn(BaseModel):
    scenario: Scenario
    k: int = Field(default=200, ge=0, le=2_000)
    seed: int = Field(default=42, ge=0)


class ImportIn(ExportIn):
    export_version: int = 1
    scenario_id: str
    result_hash: str


class SweepIn(BaseModel):
    scenario: Scenario = Field(default_factory=Scenario)
    sku_id: str
    lever: str = Field(pattern="^(price_index|promo_depth_pct)$")
    values: list[float] = Field(min_length=1, max_length=10_000)
    k: int = Field(default=200, ge=0, le=2_000)
    seed: int = Field(default=42, ge=0)
