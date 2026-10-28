"""Agent tool find_similar_runs: schema/errors only; no invented metrics."""

import pytest

from backend.agent.tools import AgentTools, ToolError
from backend.assumptions.assumptions import SKU_IDS
from backend.engine.scenario import Lever, Scenario


def test_find_similar_runs_requires_input():
    tools = AgentTools()
    with pytest.raises(ToolError, match="requires scenario"):
        tools.invoke("find_similar_runs", {})


def test_find_similar_runs_unavailable_without_database():
    tools = AgentTools()
    scenario = Scenario(name="probe", levers={SKU_IDS[0]: Lever(price_index=1.01)}).model_dump(mode="json")
    with pytest.raises(ToolError, match="DATABASE_URL|unavailable|not configured"):
        tools.invoke("find_similar_runs", {"scenario": scenario, "limit": 3})
