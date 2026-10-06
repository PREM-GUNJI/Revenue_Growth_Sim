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


class AgentRunIn(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    workspace_id: str | None = Field(default=None, max_length=64)


class ConsumerEvidenceIn(BaseModel):
    seed: int = Field(default=42, ge=0)
    sample_size: int | None = Field(default=None, ge=1, le=10000)  # None -> registry A-026


class ResearchIn(ConsumerEvidenceIn):
    methodology: str = Field(pattern="^(Willingness to Pay|Gabor-Granger|Van Westendorp Price Sensitivity Meter)$")
    prices: list[float] = Field(default_factory=list, max_length=100)
    pack: str = Field(default="pet_500ml", pattern="^(can_330ml|pet_500ml|bottle_1500ml|multipack_6x330ml)$")


class ConjointIn(ConsumerEvidenceIn):
    alternatives: list[dict] = Field(min_length=1, max_length=50)
    utilities: dict | None = None  # None -> supplied registry part-worths (A-037)
    focus_brand: str = "Aurora"


class ResearchToScenariosIn(ResearchIn):
    brand: str = "Aurora"
    promotion_depth_pct: float = Field(default=0, ge=0, le=100)


class ConjointToScenariosIn(ConjointIn):
    pass
