"""Planner/Executor/Auditor run loop shared by offline and live model providers."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from backend.agent.auditor import audit_answer
from backend.agent.schemas import AgentAnswer, AgentPlan, AgentRun, Claim, ToolEvent
from backend.agent.tools import AgentTools
from backend.agent.trace import TraceRecorder
from backend.engine.scenario import CostShock, Scenario

PROMPT_VERSION_HASH = hashlib.sha256(b"revenue-growth-agent-phase10-14-v2").hexdigest()


class ScriptedLLM:
    """Offline fake model with an explicit plan and optional draft retry queue."""

    model_id = "scripted-fake-llm"
    temperature = 0

    def __init__(self, plan: AgentPlan, drafts: list[AgentAnswer] | None = None):
        self._plan = plan
        self._drafts = list(drafts or [])

    def plan(self, goal: str, context: dict) -> AgentPlan:
        del goal, context
        return self._plan.model_copy(deep=True)

    def draft(
        self, goal: str, plan: AgentPlan, evaluated: list[dict],
        evaluation_call_id: str, ranking: list[dict], feedback: list[str] | None = None,
    ) -> AgentAnswer:
        del goal, feedback
        if self._drafts:
            return self._drafts.pop(0).model_copy(deep=True)
        refused = []
        for item in evaluated:
            if item.get("status") == "REFUSED":
                refused.extend(reason.get("message", "") for reason in item.get("refusal_reasons", []))
        if not ranking:
            return AgentAnswer(
                summary="No supported scenario produced a numeric result.",
                refusals=refused,
                caveats=["Revise the request to stay inside the observed support envelope."],
            )
        best_index = ranking[0]["index"]
        best = evaluated[best_index]
        best_name = plan.scenarios[best_index].name or "Scenario " + str(best_index + 1)
        gp_value = float(best["portfolio_gp"]["value"])
        modeled = Claim(
            claim_id="modeled-best-gp",
            text=best_name + " has modeled portfolio gross profit " + format(gp_value, ".1f") + ".",
            label="Modeled",
            tool_call_id=evaluation_call_id,
            field_path=str(best_index) + ".portfolio_gp.value",
        )
        recommended = Claim(
            claim_id="recommended-best-scenario",
            text="Prefer " + best_name + " when portfolio gross profit is the priority.",
            label="Recommended",
            references=[modeled.claim_id],
        )
        return AgentAnswer(
            summary="The comparison uses deterministic engine results.",
            recommendations=[recommended.text],
            refusals=refused,
            caveats=["Modeled values depend on documented assumptions; sensitivity bands are not confidence intervals."],
            claims=[modeled, recommended],
        )


class AgentOrchestrator:
    def __init__(self, max_audit_retries: int = 2):
        if max_audit_retries < 0:
            raise ValueError("max_audit_retries must be non-negative")
        self.max_audit_retries = max_audit_retries

    def run(self, goal: str, llm: Any, trace_path: str | Path | None = None) -> AgentRun:
        wall_started = time.perf_counter()
        model_time_ms = 0.0
        tool_time_ms = 0.0
        tools = AgentTools()

        def invoke(name: str, arguments: dict):
            nonlocal tool_time_ms
            started = time.perf_counter()
            result = tools.invoke(name, arguments)
            tool_time_ms += (time.perf_counter() - started) * 1000
            return result

        envelope_id, envelope = invoke("get_envelope", {})
        assumptions_id, assumptions = invoke("get_assumptions", {})
        model_call_id, model_info = invoke("get_model_info", {})
        model_started = time.perf_counter()
        plan = llm.plan(goal, {
            "envelope": envelope, "envelope_tool_call_id": envelope_id,
            "assumptions": assumptions, "assumptions_tool_call_id": assumptions_id,
            "model_info": model_info, "model_info_tool_call_id": model_call_id,
        })
        model_time_ms += (time.perf_counter() - model_started) * 1000
        if not isinstance(plan, AgentPlan):
            plan = AgentPlan.model_validate(plan)
        scenarios = list(plan.scenarios)
        has_baseline = any(
            not item.levers and not any(item.cost_shock.model_dump().values())
            for item in scenarios
        )
        if not has_baseline:
            scenarios.insert(0, Scenario(name="Baseline"))
        if not any(
            item.cost_shock.model_dump() == {
                "aluminium_pct": 8.0, "pet_resin_pct": 8.0, "sugar_pct": 8.0
            }
            for item in scenarios
        ):
            scenarios.append(Scenario(
                name="Downside input-cost stress",
                cost_shock=CostShock(aluminium_pct=8, pet_resin_pct=8, sugar_pct=8),
            ))
        plan = AgentPlan(scenarios=scenarios, objective=plan.objective)
        eval_id, evaluated = invoke("evaluate_scenarios", {
            "scenarios": [scenario.model_dump(mode="json") for scenario in plan.scenarios],
            "k": 200, "seed": 42,
        })
        _ranking_call_id, ranking = invoke(
            "rank_scenarios", {"results": evaluated, "metric": "portfolio_gp"}
        )
        invoke("pareto_flags", {"results": evaluated})
        for result, scenario in zip(evaluated, plan.scenarios, strict=True):
            if result.get("status") == "REFUSED":
                invoke("nearest_supported", {"scenario": scenario.model_dump(mode="json")})
            else:
                invoke("explain_scenario", {
                    "scenario": scenario.model_dump(mode="json"), "k": 0, "seed": 42,
                })

        events = [ToolEvent.model_validate(item) for item in tools.events]
        answer = AgentAnswer(summary="Auditor did not produce a draft.")
        verdict = audit_answer(answer, events)
        feedback: list[str] = []
        for _ in range(self.max_audit_retries + 1):
            model_started = time.perf_counter()
            answer = llm.draft(goal, plan, evaluated, eval_id, ranking, feedback)
            model_time_ms += (time.perf_counter() - model_started) * 1000
            if not isinstance(answer, AgentAnswer):
                answer = AgentAnswer.model_validate(answer)
            verdict = audit_answer(answer, events)
            if verdict.passed:
                break
            feedback = verdict.issues

        recorder = TraceRecorder(llm.model_id, PROMPT_VERSION_HASH, temperature=llm.temperature)
        recorder.record_tool_events(tools.events)
        recorder.record_final(answer, verdict.model_dump(mode="json"))
        if trace_path is not None:
            recorder.write(trace_path)
        return AgentRun(
            answer=answer, audit=verdict, tool_events=events,
            model_id=llm.model_id, prompt_version_hash=PROMPT_VERSION_HASH,
            temperature=llm.temperature, scenarios=plan.scenarios,
            wall_time_ms=(time.perf_counter() - wall_started) * 1000,
            model_time_ms=model_time_ms, tool_time_ms=tool_time_ms,
        )


def demo_plan() -> AgentPlan:
    """Reproducible comparison plan for local use of the scripted implementation."""
    sku = "Aurora-can_330ml"
    baseline = Scenario(name="Baseline")
    price = Scenario(name="Defensive price move", levers={
        sku: {"price_index": 1.04, "promo_depth_pct": 0, "mechanic": "none", "promo_weeks_per_month": 0},
    })
    promotion = Scenario(name="Promotion control", levers={
        sku: {"price_index": 1.0, "promo_depth_pct": 20, "mechanic": "TPR", "promo_weeks_per_month": 2},
    })
    refused = Scenario(name="Out-of-range price request", levers={
        sku: {"price_index": 1.5, "promo_depth_pct": 0, "mechanic": "none", "promo_weeks_per_month": 0},
    })
    return AgentPlan(scenarios=[baseline, price, promotion, refused], objective="compare modeled margin outcomes")
