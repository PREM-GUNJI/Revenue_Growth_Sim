"""Typed allowlist of deterministic tools exposed to the scripted agent."""

from __future__ import annotations

import ast
import hashlib
import json
import operator
from dataclasses import asdict
from typing import Any

from backend.assumptions.assumptions import (
    ASSUMPTIONS, CROSS_ELASTICITY_ACROSS_BRAND, CROSS_ELASTICITY_WITHIN_BRAND,
    OWN_ELASTICITY_BY_FORMAT, PROMO_LIFT_SCALE, PROMO_MECHANIC_MULTIPLIER,
    PROMO_SATURATION_K, PULL_FORWARD_SHARE, SKUS, SKU_IDS,
)
from backend.engine.batch import ENGINE_VERSION, _data_hash, _support_envelope, evaluate_batch
from backend.engine.ids import expand_scenario, scenario_id
from backend.engine.scenario import Lever, Scenario
from backend.engine.support import nearest_supported
from backend.model.backtest import spec_hash
from backend.model.spec import ParamDraws, build_param_draws


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
            {**asdict(result), "scenario": scenario.model_dump(mode="json")}
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
        return {"scenario_id": result.scenario_id, "status": result.status,
                "bridge": {sku: asdict(bridge) for sku, bridge in result.bridge.items()},
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

    def _tool_rank_scenarios(self, results: list[dict], metric: str = "portfolio_gp") -> list[dict]:
        if metric not in {"portfolio_gp", "volume"}:
            raise ToolError("rank metric must be portfolio_gp or volume")
        rows = []
        for index, item in enumerate(results):
            if item.get("status") == "REFUSED":
                continue
            score = item["portfolio_gp"]["value"] if metric == "portfolio_gp" else sum(x["value"] for x in item["volume"].values())
            rows.append({"index": index, "scenario_id": item["scenario_id"], "score": score})
        return sorted(rows, key=lambda row: (-row["score"], row["index"]))

    def _tool_pareto_flags(self, results: list[dict]) -> list[dict]:
        rows = [(i, item) for i, item in enumerate(results)
                if item.get("status") != "REFUSED" and item.get("portfolio_gp") is not None]
        output = []
        for index, item in rows:
            gp = item["portfolio_gp"]["value"]
            volume = sum(value["value"] for value in item["volume"].values())
            dominated = any(
                other_index != index and other["portfolio_gp"]["value"] >= gp
                and sum(value["value"] for value in other["volume"].values()) >= volume
                and (other["portfolio_gp"]["value"] > gp or sum(value["value"] for value in other["volume"].values()) > volume)
                for other_index, other in rows
            )
            output.append({"index": index, "scenario_id": item["scenario_id"], "dominated": dominated})
        return output
