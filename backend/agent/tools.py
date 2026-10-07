"""Typed allowlist of deterministic tools exposed to the scripted agent."""

from __future__ import annotations

import ast
import hashlib
import json
import operator
from dataclasses import asdict
from typing import Any

from backend.assumptions.assumptions import (
    ASSUMPTIONS,
    CROSS_ELASTICITY_ACROSS_BRAND,
    CROSS_ELASTICITY_WITHIN_BRAND,
    OWN_ELASTICITY_BY_FORMAT,
    PROMO_LIFT_SCALE,
    PROMO_MECHANIC_MULTIPLIER,
    PROMO_SATURATION_K,
    PULL_FORWARD_SHARE,
    SKU_IDS,
    SKUS,
)
from backend.engine.batch import ENGINE_VERSION, _data_hash, _support_envelope, evaluate_batch
from backend.engine.explain import assumption_ids_for, focal_bridge
from backend.engine.ids import expand_scenario, scenario_id
from backend.engine.scenario import Lever, Scenario
from backend.engine.support import nearest_supported
from backend.model.backtest import spec_hash
from backend.model.spec import ParamDraws, build_param_draws
from backend.research.evidence import (
    CONJOINT_METHOD,
    LABEL,
    conjoint_simulation,
    default_conjoint_alternatives,
    generate_consumers,
    research_to_scenarios,
    run_research,
    summarize_consumers,
)
from backend.situation import compact_for_agent


class ToolError(ValueError):
    """Invalid tool name, input, or unsupported calculation."""


def _to_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return json.loads(json.dumps(value, default=lambda item: asdict(item) if hasattr(item, "__dataclass_fields__") else str(item)))


def _hash(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _get_path(value: Any, path: str) -> Any:
    for token in path.split("."):
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def _override(draws: ParamDraws, assumption_id: str, value: float) -> None:
    own = {assumption.id: fmt for fmt, assumption in OWN_ELASTICITY_BY_FORMAT.items()}
    if assumption_id in own:
        for index, sku in enumerate(SKUS):
            if sku["format"] == own[assumption_id]:
                draws.elasticity[:, index, index] = value
        return
    for assumption, brand_match in ((CROSS_ELASTICITY_WITHIN_BRAND, True), (CROSS_ELASTICITY_ACROSS_BRAND, False)):
        if assumption_id == assumption.id:
            for i, left in enumerate(SKUS):
                for j, right in enumerate(SKUS):
                    if i != j and ((left["brand"] == right["brand"]) == brand_match):
                        draws.elasticity[:, i, j] = value
            return
    arrays = {
        PROMO_SATURATION_K.id: draws.promo_k,
        PROMO_LIFT_SCALE.id: draws.promo_b,
        PULL_FORWARD_SHARE.id: draws.pull_forward_share,
    }
    arrays.update({item.id: draws.mech_mult[name] for name, item in PROMO_MECHANIC_MULTIPLIER.items()})
    if assumption_id not in arrays:
        raise ToolError(f"{assumption_id} is not a supported sensitivity parameter")
    arrays[assumption_id][:] = value


class AgentTools:
    """No filesystem, subprocess, or network capabilities are exposed to the agent."""

    def __init__(self):
        self.events: list[dict] = []
        self._counter = 1

    def invoke(self, name: str, arguments: dict[str, Any]) -> tuple[str, Any]:
        function = getattr(self, "_tool_" + name, None)
        if function is None:
            raise ToolError(f"unknown tool {name!r}")
        call_id = "call_" + str(self._counter).zfill(4)
        self._counter += 1
        result = _to_json(function(**arguments))
        event = {"call_id": call_id, "name": name, "arguments": _to_json(arguments),
                 "result": result, "result_hash": _hash(result)}
        self.events.append(event)
        return call_id, result

    def _tool_get_assumptions(self, ids: list[str] | None = None) -> list[dict]:
        selected = set(ASSUMPTIONS) if ids is None else set(ids)
        missing = selected - set(ASSUMPTIONS)
        if missing:
            raise ToolError("unknown assumption ids: " + ", ".join(sorted(missing)))
        return [asdict(ASSUMPTIONS[item]) for item in sorted(selected)]

    def _tool_get_model_info(self) -> dict:
        return {"engine_version": ENGINE_VERSION, "data_hash": _data_hash(),
                "model_spec_hash": spec_hash(), "deterministic": True}

    def _tool_get_baseline(self) -> dict:
        """Where the focal brand stands today: baseline P&L per pack and engine probes of price, promo and cost moves."""
        return compact_for_agent()

    def _tool_get_pricing_methodologies(self) -> dict:
        return {"priority_1": ["Willingness to Pay", "Gabor-Granger",
                               "Van Westendorp Price Sensitivity Meter"],
                "priority_2": ["Conjoint simulation (supplied utilities)"],
                "role": "Research proposes candidate prices only; the engine computes volume, revenue and margin.",
                "label": LABEL}

    def _tool_get_consumer_evidence(self, seed: int = 42, sample_size: int | None = None) -> dict:
        return summarize_consumers(generate_consumers(seed, sample_size))

    def _tool_run_wtp(self, seed: int = 42, sample_size: int | None = None, pack: str = "pet_500ml") -> dict:
        return asdict(run_research("Willingness to Pay", generate_consumers(seed, sample_size), None, pack))

    def _tool_run_gabor_granger(self, prices: list[float] | None = None, seed: int = 42,
                                sample_size: int | None = None, pack: str = "pet_500ml") -> dict:
        return asdict(run_research("Gabor-Granger", generate_consumers(seed, sample_size), prices, pack))

    def _tool_run_van_westendorp(self, seed: int = 42, sample_size: int | None = None,
                                 pack: str = "pet_500ml") -> dict:
        return asdict(run_research("Van Westendorp Price Sensitivity Meter",
                                   generate_consumers(seed, sample_size), None, pack))

    def _tool_run_conjoint_simulation(self, alternatives: list[dict] | None = None, brand: str = "Aurora",
                                      pack: str = "pet_500ml", seed: int = 42,
                                      sample_size: int | None = None) -> dict:
        # No utilities argument: the agent cannot invent part-worths; the registry supplies them.
        alternatives = alternatives or default_conjoint_alternatives(brand, pack)
        return asdict(conjoint_simulation(generate_consumers(seed, sample_size), alternatives, None, brand))

    def _tool_research_to_scenarios(self, methodology: str = "Willingness to Pay", seed: int = 42,
                                    sample_size: int | None = None, prices: list[float] | None = None,
                                    brand: str = "Aurora", pack: str = "pet_500ml",
                                    promotion_depth_pct: float = 0,
                                    alternatives: list[dict] | None = None) -> list[dict]:
        evidence = generate_consumers(seed, sample_size)
        if methodology == CONJOINT_METHOD:
            research = conjoint_simulation(evidence, alternatives or default_conjoint_alternatives(brand, pack), None, brand)
        else:
            research = run_research(methodology, evidence, prices, pack)
        return research_to_scenarios(research, brand, promotion_depth_pct)

    def _tool_get_envelope(self) -> dict:
        env = _support_envelope()
        return {"sku_ids": SKU_IDS, "price_index_p1_p99": env.baselines.price_index_p1_p99,
                "promo_depth_observed": env.baselines.promo_depth_observed,
                "formats": env.coverage.formats, "mechanics": env.coverage.mechanics,
                "depth_steps": env.coverage.depth_steps,
                "price_bin_edges": env.coverage.price_bin_edges.tolist()}

    def _tool_evaluate_scenarios(self, scenarios: list[dict], k: int = 0, seed: int = 42) -> list[dict]:
        requests = [Scenario.model_validate(item) for item in scenarios]
        results = evaluate_batch(requests, build_param_draws(k=k, seed=seed))
        return [
            {**asdict(result), "scenario": scenario.model_dump(mode="json"),
             "assumption_ids": assumption_ids_for(scenario), "focal_bridge": focal_bridge(result, major_units=True)}
            for scenario, result in zip(requests, results, strict=True)
        ]

    def _tool_sweep(self, scenario: dict, sku_id: str, lever: str, values: list[float], k: int = 0, seed: int = 42) -> list[dict]:
        if sku_id not in SKU_IDS or lever not in {"price_index", "promo_depth_pct"}:
            raise ToolError("sweep requires a known SKU and a supported lever")
        base = Scenario.model_validate(scenario)
        before = base.levers.get(sku_id, Lever())
        requests = []
        for value in values:
            changed = before.model_copy(deep=True)
            if lever == "price_index":
                changed.price_index = value
            else:
                changed.promo_depth_pct = value
                changed.mechanic = "none" if value == 0 else ("TPR" if before.mechanic == "none" else before.mechanic)
                changed.promo_weeks_per_month = 0 if value == 0 else max(1, before.promo_weeks_per_month)
            item = base.model_copy(deep=True)
            item.levers[sku_id] = changed
            requests.append(item)
        results = evaluate_batch(requests, build_param_draws(k=k, seed=seed))
        return [
            {**asdict(result), "scenario": scenario.model_dump(mode="json")}
            for scenario, result in zip(requests, results, strict=True)
        ]

    def _tool_nearest_supported(self, scenario: dict) -> dict:
        item = Scenario.model_validate(scenario)
        suggestion = nearest_supported(item, _support_envelope())
        status = _support_envelope().check(suggestion.scenario).status
        if status == "REFUSED":
            raise ToolError("nearest-supported invariant failed")
        return {"scenario": suggestion.scenario.model_dump(mode="json"),
                "scenario_id": scenario_id(expand_scenario(suggestion.scenario)),
                "distance": suggestion.distance, "status": status}

    def _tool_explain_scenario(self, scenario: dict, k: int = 0, seed: int = 42) -> dict:
        result = evaluate_batch([Scenario.model_validate(scenario)], build_param_draws(k=k, seed=seed))[0]
        scenario_model = Scenario.model_validate(scenario)
        return {"scenario_id": result.scenario_id, "status": result.status,
                "bridge": {sku: asdict(bridge) for sku, bridge in result.bridge.items()},
                "focal_bridge": focal_bridge(result, major_units=True),
                "assumption_ids": assumption_ids_for(scenario_model),
                "refusal_reasons": result.refusal_reasons}

    def _tool_run_sensitivity(self, scenario: dict, assumption_id: str, value: float) -> dict:
        assumption = ASSUMPTIONS.get(assumption_id)
        if assumption is None or assumption.valid_range is None:
            raise ToolError(f"{assumption_id} has no numeric valid range")
        low, high = assumption.valid_range
        if not low <= value <= high:
            raise ToolError(f"value outside {assumption_id} range [{low}, {high}]")
        draws = build_param_draws(k=0, seed=42)
        _override(draws, assumption_id, value)
        result = evaluate_batch([Scenario.model_validate(scenario)], draws)[0]
        return {"tag": "SENSITIVITY", "assumption_id": assumption_id,
                "value": value, "result": asdict(result)}

    def _tool_sensitivity(self, scenarios: list[dict], seed: int = 42) -> dict:
        from backend.analysis import sensitivity
        return sensitivity([Scenario.model_validate(item) for item in scenarios], seed)

    def _tool_goal_seek(self, max_volume_loss_pct: float = 5.0, sku_ids: list[str] | None = None, top: int = 5) -> dict:
        from backend.analysis import goal_seek
        return goal_seek(max_volume_loss_pct, sku_ids, top)

    def _tool_calc(self, expression: str, bindings: dict[str, dict[str, str]]) -> dict:
        values = {}
        for alias, source in bindings.items():
            event = next((item for item in self.events if item["call_id"] == source["tool_call_id"]), None)
            if event is None:
                raise ToolError("calc source tool call is unknown")
            value = _get_path(event["result"], source["field_path"])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ToolError("calc source field is not numeric")
            values[alias] = float(value)
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
        def walk(node):
            if isinstance(node, ast.Expression):
                return walk(node.body)
            if isinstance(node, ast.Name) and node.id in values:
                return values[node.id]
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                left, right = walk(node.left), walk(node.right)
                if isinstance(node.op, ast.Div) and right == 0:
                    raise ToolError("division by zero")
                return ops[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                result = walk(node.operand)
                return result if isinstance(node.op, ast.UAdd) else -result
            raise ToolError("calc accepts only bound values and +, -, *, /")
        result = float(walk(ast.parse(expression, mode="eval")))
        return {"expression": expression, "value": result, "source_bindings": bindings}

    def _tool_save_scenario(self, scenario: dict) -> dict:
        item = Scenario.model_validate(scenario)
        return {"status": "agent-proposed", "scenario": item.model_dump(mode="json"),
                "scenario_id": scenario_id(expand_scenario(item))}

    def _tool_rank_scenarios(self, results: list[dict], metric: str = "focal_gp") -> list[dict]:
        """Best first. The default is the focal brand's gross profit: competitor brands' profit is not ours."""
        if metric not in {"focal_gp", "focal_volume", "portfolio_gp", "volume"}:
            raise ToolError("rank metric must be focal_gp, focal_volume, portfolio_gp or volume")
        rows = []
        for index, item in enumerate(results):
            if item.get("status") == "REFUSED":
                continue
            if metric == "focal_gp":
                score = item["focal"]["gp"]["value"]
            elif metric == "focal_volume":
                score = item["focal"]["volume"]["value"]
            elif metric == "portfolio_gp":
                score = item["portfolio_gp"]["value"]
            else:
                score = sum(x["value"] for x in item["volume"].values())
            rows.append({"index": index, "scenario_id": item["scenario_id"], "score": score})
        return sorted(rows, key=lambda row: (-row["score"], row["index"]))

    def _tool_pareto_flags(self, results: list[dict]) -> list[dict]:
        """A scenario is dominated when another has at least the focal brand's gross profit and volume, and more of one."""
        rows = [(i, item) for i, item in enumerate(results)
                if item.get("status") != "REFUSED" and item.get("focal")]
        output = []
        for index, item in rows:
            gp, volume = item["focal"]["gp"]["value"], item["focal"]["volume"]["value"]
            dominated = any(
                other_index != index and other["focal"]["gp"]["value"] >= gp
                and other["focal"]["volume"]["value"] >= volume
                and (other["focal"]["gp"]["value"] > gp or other["focal"]["volume"]["value"] > volume)
                for other_index, other in rows
            )
            output.append({"index": index, "scenario_id": item["scenario_id"], "dominated": dominated})
        return output
