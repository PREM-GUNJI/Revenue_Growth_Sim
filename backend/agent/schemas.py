"""Typed structured outputs shared by the planner, tools, Auditor, and trace layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.engine.scenario import CostShock, Lever, Scenario

ClaimLabel = Literal["Observed", "Modeled", "Assumed", "Recommended"]


class AgentPlan(BaseModel):
    scenarios: list[Scenario] = Field(min_length=4, max_length=6)
    objective: str = ""


class SkuLever(BaseModel):
    """One (sku_id, lever) pair. OpenAI structured outputs reject Scenario.levers'
    dict[str, Lever] shape (arbitrary-keyed objects aren't representable in strict
    JSON schema), so the planner emits a list of pairs instead and we assemble the
    dict ourselves before constructing the real engine Scenario."""

    sku_id: str
    lever: Lever


class PlannerScenario(BaseModel):
    name: str = Field(default="", max_length=80)
    sku_levers: list[SkuLever] = Field(default_factory=list)
    cost_shock: CostShock = Field(default_factory=CostShock)

    def to_scenario(self) -> Scenario:
        return Scenario(
            name=self.name,
            levers={pair.sku_id: pair.lever for pair in self.sku_levers},
            cost_shock=self.cost_shock,
        )


class PlannerPlan(BaseModel):
    scenarios: list[PlannerScenario] = Field(min_length=4, max_length=6)
    objective: str = ""

    def to_agent_plan(self) -> AgentPlan:
        return AgentPlan(
            scenarios=[s.to_scenario() for s in self.scenarios],
            objective=self.objective,
        )


class Claim(BaseModel):
    claim_id: str
    text: str
    label: ClaimLabel
    tool_call_id: str | None = None
    field_path: str | None = None
    references: list[str] = Field(default_factory=list)


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
    wall_time_ms: float = 0.0
    model_time_ms: float = 0.0
    tool_time_ms: float = 0.0
