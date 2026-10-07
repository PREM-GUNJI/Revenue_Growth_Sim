"""Typed structured outputs shared by the planner, tools, Auditor, and trace layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.assumptions.assumptions import BRANDS, PROMO_MECHANICS, SKU_IDS
from backend.engine.scenario import CostShock, Lever, Scenario

ClaimLabel = Literal["Observed", "Modeled", "Assumed", "Recommended"]


Methodology = Literal[
    "Willingness to Pay", "Gabor-Granger", "Van Westendorp Price Sensitivity Meter",
    "Conjoint simulation (supplied utilities)",
]
Pack = Literal["can_330ml", "pet_500ml", "bottle_1500ml", "multipack_6x330ml"]
# Brands come from the registry list; free text here let the model invent one ("ALL_500ml") that no SKU has.
Brand = Literal[tuple(BRANDS)]  # type: ignore[valid-type]
SkuId = Literal[tuple(SKU_IDS)]  # type: ignore[valid-type]


class ConjointAlt(BaseModel):
    """A configuration to compare. Utilities are never supplied by the agent."""

    brand: Brand  # type: ignore[valid-type]
    pack: Pack
    price: float = Field(gt=0)
    promotion: str = "None"


class ResearchPlan(BaseModel):
    """Which supporting evidence to gather. Produces candidates only; the engine computes outcomes."""

    methodology: Methodology
    pack: Pack = "pet_500ml"
    brand: Brand = "Aurora"  # type: ignore[valid-type]
    promotion_depth_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    alternatives: list[ConjointAlt] = Field(default_factory=list, max_length=8)


class AgentPlan(BaseModel):
    # PlannerPlan keeps the model to 4-6 scenarios; research candidates and the
    # mandatory baseline/stress scenarios are added by the orchestrator.
    scenarios: list[Scenario] = Field(min_length=4, max_length=16)
    objective: str = ""
    research: ResearchPlan | None = None


# The planner's structured-output schema must list the allowed mechanics, otherwise the model writes
# free text such as "temporary_price_reduction". The values come from the registry list, not a copy.
Mechanic = Literal[tuple(PROMO_MECHANICS)]  # type: ignore[valid-type]


class PlannerLever(Lever):
    """The engine Lever, with `mechanic` restricted to the registry's promo mechanics for the model's schema."""

    mechanic: Mechanic = "none"  # type: ignore[assignment,valid-type]


class SkuLever(BaseModel):
    """One (sku_id, lever) pair. OpenAI structured outputs reject Scenario.levers'
    dict[str, Lever] shape (arbitrary-keyed objects aren't representable in strict
    JSON schema), so the planner emits a list of pairs instead and we assemble the
    dict ourselves before constructing the real engine Scenario."""

    sku_id: SkuId  # type: ignore[valid-type]
    lever: PlannerLever


class PlannerScenario(BaseModel):
    name: str = Field(default="", max_length=80)
    sku_levers: list[SkuLever] = Field(default_factory=list)
    cost_shock: CostShock = Field(default_factory=CostShock)

    def to_scenario(self) -> Scenario:
        return Scenario(
            name=self.name,
            levers={pair.sku_id: Lever(**pair.lever.model_dump()) for pair in self.sku_levers},
            cost_shock=self.cost_shock,
        )


class PlannerPlan(BaseModel):
    scenarios: list[PlannerScenario] = Field(min_length=4, max_length=6)
    objective: str = ""
    research: ResearchPlan | None = None

    def to_agent_plan(self) -> AgentPlan:
        return AgentPlan(
            scenarios=[s.to_scenario() for s in self.scenarios],
            objective=self.objective,
            research=self.research,
        )


class Claim(BaseModel):
    claim_id: str
    text: str
    label: ClaimLabel
    tool_call_id: str | None = None
    field_path: str | None = None
    references: list[str] = Field(default_factory=list)
    research_id: str | None = None  # required for research-derived Modeled claims


class AgentAnswer(BaseModel):
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)


class AuditVerdict(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    numbers_checked: int = 0


class ToolEvent(BaseModel):
    call_id: str
    name: str
    arguments: dict
    result: object
    result_hash: str


class AgentRun(BaseModel):
    answer: AgentAnswer
    audit: AuditVerdict
    tool_events: list[ToolEvent]
    model_id: str
    prompt_version_hash: str
    temperature: Literal[0] = 0
    scenarios: list[Scenario] = Field(default_factory=list)
    # Refused scenarios -> engine-evaluated nearest supported scenario (numbers come from the tool, never the model).
    alternatives: list[dict] = Field(default_factory=list)
    wall_time_ms: float = 0.0
    model_time_ms: float = 0.0
    tool_time_ms: float = 0.0
