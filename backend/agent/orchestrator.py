"""Planner/Executor/Auditor run loop shared by offline and live model providers."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Any

from backend.agent.auditor import audit_answer
from backend.agent.schemas import AgentAnswer, AgentPlan, AgentRun, Claim, ToolEvent
from backend.agent.tools import AgentTools
from backend.agent.trace import TraceRecorder
from backend.engine.scenario import CostShock, Scenario

# v3: focal-brand objective, baseline context for the planner, bridge and assumption ids in results.
PROMPT_VERSION_HASH = hashlib.sha256(b"revenue-growth-agent-phase10-14-v3").hexdigest()


def _research_claims(research: dict, ranking: list[dict], evaluation_call_id: str) -> list[Claim]:
    """Research-derived claim (candidate price) + engine claim (its modeled outcome), both traceable."""
    by_scenario = dict(zip(research["scenario_indices"], research["candidate_indices"], strict=True))
    for row in ranking:  # best-first and already excludes refused scenarios
        if row["index"] in by_scenario:
            scenario_index, candidate_index = row["index"], by_scenario[row["index"]]
            break
    else:
        return []
    return [
        Claim(claim_id="research-candidate-price",
              text="The " + research["methodology"] + " study proposes a candidate price of "
              + format(research["candidate_prices"][candidate_index], ".1f") + ".",
              label="Modeled", tool_call_id=research["research_call_id"],
              field_path=f"candidates.{candidate_index}.price", research_id=research["research_id"]),
        Claim(claim_id="modeled-research-candidate-gp",
              text="That research candidate has modeled gross profit for the focal brand "
              + format(float(research["gp_by_scenario"][scenario_index]), ".1f") + ".",
              label="Modeled", tool_call_id=evaluation_call_id,
              field_path=f"{scenario_index}.focal.gp.value"),
    ]


_VOLUME_CAP = re.compile(r"(?:los\w*|drop\w*|fall\w*|decline\w*)[^.%]{0,40}?(\d+(?:\.\d+)?)\s*%[^.]{0,15}volume|volume[^.%]{0,40}?(\d+(?:\.\d+)?)\s*%", re.I)


def _volume_cap(goal: str) -> float | None:
    """A stated volume-loss limit in the goal ("without losing more than 5% volume") turns the run into a goal-seek."""
    match = _VOLUME_CAP.search(goal)
    return None if match is None else float(match.group(1) or match.group(2))


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
        research: dict | None = None,
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
        # Scenario names are untrusted data (CLAUDE.md: "never instructions"), and may
        # contain injected text or stray digits that would fail numeric grounding (or
        # leak the payload verbatim) if echoed into narrative claim text. Never embed
        # the user-supplied name, or any index-derived digit, in generated prose; the
        # name still appears unmodified in tool_events/plan.scenarios for the UI/trace.
        best_name = "the top-ranked scenario"
        gp_value = float(best["focal"]["gp"]["value"])
        modeled = Claim(
            claim_id="modeled-best-gp",
            text=best_name + " has modeled gross profit for the focal brand " + format(gp_value, ".1f") + ".",
            label="Modeled",
            tool_call_id=evaluation_call_id,
            field_path=str(best_index) + ".focal.gp.value",
        )
        recommended = Claim(
            claim_id="recommended-best-scenario",
            text="Prefer " + best_name + " when gross profit for the focal brand is the priority.",
            label="Recommended",
            references=[modeled.claim_id],
        )
        claims = [modeled, recommended]
        caveats = ["Modeled values depend on documented assumptions; sensitivity bands are not confidence intervals."]
        if research:
            claims += _research_claims(research, ranking, evaluation_call_id)
            caveats.append("Consumer evidence is synthetic and illustrative. It proposed candidate prices only; "
                           "every volume, revenue and margin figure comes from the deterministic engine.")
        return AgentAnswer(
            summary="The comparison uses deterministic engine results.",
            recommendations=[recommended.text],
            refusals=refused,
            caveats=caveats,
            claims=claims,
        )


_RESEARCH_TOOLS = {
    "Willingness to Pay": "run_wtp",
    "Gabor-Granger": "run_gabor_granger",
    "Van Westendorp Price Sensitivity Meter": "run_van_westendorp",
    "Conjoint simulation (supplied utilities)": "run_conjoint_simulation",
}


class AgentOrchestrator:
    @staticmethod
    def _gather_research(research, invoke, scenarios: list[Scenario]) -> dict:
        """Evidence tools -> candidate scenarios. Research never produces commercial numbers."""
        invoke("get_pricing_methodologies", {})
        base_args: dict = {"pack": research.pack}
        if research.methodology.startswith("Conjoint"):
            base_args["brand"] = research.brand
            if research.alternatives:
                base_args["alternatives"] = [item.model_dump(mode="json") for item in research.alternatives]
        research_call_id, result = invoke(_RESEARCH_TOOLS[research.methodology], base_args)
        mapping_args = {"methodology": research.methodology, "brand": research.brand, "pack": research.pack,
                        "promotion_depth_pct": research.promotion_depth_pct,
                        **({"alternatives": base_args["alternatives"]} if "alternatives" in base_args else {})}
        _mapping_id, rows = invoke("research_to_scenarios", mapping_args)
        scenario_indices, candidate_indices = [], []
        for row in rows:
            scenario_indices.append(len(scenarios))
            candidate_indices.append(row["provenance"]["candidate_index"])
            scenarios.append(Scenario.model_validate(row["scenario"]))
        return {"research_call_id": research_call_id, "research_id": result["research_id"],
                "methodology": result["methodology"], "scenario_indices": scenario_indices,
                "candidate_indices": candidate_indices,
                "candidate_prices": [item["price"] for item in result["candidates"]],
                "provenance": [row["provenance"] for row in rows]}

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
        baseline_call_id, baseline = invoke("get_baseline", {})
        model_started = time.perf_counter()
        plan = llm.plan(goal, {
            "envelope": envelope, "envelope_tool_call_id": envelope_id,
            "assumptions": assumptions, "assumptions_tool_call_id": assumptions_id,
            "model_info": model_info, "model_info_tool_call_id": model_call_id,
            "baseline": baseline, "baseline_tool_call_id": baseline_call_id,
        })
        model_time_ms += (time.perf_counter() - model_started) * 1000
        if not isinstance(plan, AgentPlan):
            plan = AgentPlan.model_validate(plan)
        scenarios = list(plan.scenarios)
        research_context = None
        if plan.research is not None:
            research_context = self._gather_research(plan.research, invoke, scenarios)
        cap = _volume_cap(goal)
        if cap is not None and plan.research is None:
            _gs_id, found = invoke("goal_seek", {"max_volume_loss_pct": cap, "top": 3})
            room = 14 - len(scenarios)  # keep room for the baseline and the stress scenario
            for number, item in enumerate(found["top"][:max(room, 0)], 1):
                scenarios.append(Scenario.model_validate({**item["scenario"], "name": f"Goal-seek option {number}"}))
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
            "rank_scenarios", {"results": evaluated, "metric": "focal_gp"}
        )
        invoke("pareto_flags", {"results": evaluated})
        invoke("sensitivity", {"scenarios": [scenario.model_dump(mode="json") for scenario in plan.scenarios]})
        nearest_by_index: dict[int, dict] = {}
        for index, (result, scenario) in enumerate(zip(evaluated, plan.scenarios, strict=True)):
            if result.get("status") == "REFUSED":
                _nid, nearest = invoke("nearest_supported", {"scenario": scenario.model_dump(mode="json")})
                nearest_by_index[index] = nearest
            else:
                invoke("explain_scenario", {
                    "scenario": scenario.model_dump(mode="json"), "k": 0, "seed": 42,
                })

        alternatives: list[dict] = []
        if nearest_by_index:
            order = list(nearest_by_index)
            alt_call_id, alt_results = invoke("evaluate_scenarios", {
                "scenarios": [nearest_by_index[i]["scenario"] for i in order], "k": 200, "seed": 42})
            alternatives = [{"refused_index": i, "tool_call_id": alt_call_id, "result_index": n,
                             "distance": nearest_by_index[i]["distance"], "result": alt_results[n]}
                            for n, i in enumerate(order)]

        if research_context is not None:
            gp = {i: evaluated[i]["focal"]["gp"]["value"] for i in research_context["scenario_indices"]
                  if evaluated[i].get("focal")}
            research_context["gp_by_scenario"] = gp
            # Refused candidates have no modeled numbers and can never be cited.
            keep = [(s_i, c_i) for s_i, c_i in zip(research_context["scenario_indices"],
                                                   research_context["candidate_indices"], strict=True) if s_i in gp]
            research_context["scenario_indices"] = [item[0] for item in keep]
            research_context["candidate_indices"] = [item[1] for item in keep]

        events = [ToolEvent.model_validate(item) for item in tools.events]
        answer = AgentAnswer(summary="Auditor did not produce a draft.")
        verdict = audit_answer(answer, events)
        feedback: list[str] = []
        for _ in range(self.max_audit_retries + 1):
            model_started = time.perf_counter()
            extra = {"research": research_context} if research_context is not None else {}
            answer = llm.draft(goal, plan, evaluated, eval_id, ranking, feedback, **extra)
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
            alternatives=alternatives,
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


def select_research(goal: str, pack: str = "pet_500ml"):
    """Deterministic evidence-method choice for the offline planner; None means no research is needed."""
    from backend.agent.schemas import ResearchPlan

    text = goal.lower()
    rules = (
        ("Conjoint simulation (supplied utilities)", ("conjoint", "trade-off", "tradeoff", "brand", "preference", "choice")),
        ("Van Westendorp Price Sensitivity Meter", ("van westendorp", "too expensive", "too cheap", "acceptable range", "price range")),
        ("Gabor-Granger", ("gabor", "acceptance", "demand curve", "price points")),
        ("Willingness to Pay", ("willingness to pay", "wtp", "price ceiling", "how much would")),
    )
    for methodology, words in rules:
        if any(word in text for word in words):
            return ResearchPlan(methodology=methodology, pack=pack)
    return None
