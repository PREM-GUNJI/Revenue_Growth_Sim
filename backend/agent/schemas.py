"""Typed structured outputs shared by the planner, tools, Auditor, and trace layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.engine.scenario import Scenario

ClaimLabel = Literal["Observed", "Modeled", "Assumed", "Recommended"]


class AgentPlan(BaseModel):
    scenarios: list[Scenario] = Field(min_length=4, max_length=6)
    objective: str = ""


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
