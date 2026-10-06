from __future__ import annotations

from backend.agent.openai_llm import OpenAILLM
from backend.agent.schemas import PlannerPlan


class FakeResponse:
    output_parsed = PlannerPlan(
        scenarios=[
            {"name": "A"},
            {"name": "B"},
            {"name": "C"},
            {"name": "D"},
        ]
    )


class FakeResponses:
    def __init__(self):
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_model_id_and_structured_response_are_read_from_configuration(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.5")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = FakeClient()
    model = OpenAILLM(client=client)
    plan = model.plan("Compare options", {"sku_ids": ["Aurora-can_330ml"]})
    assert model.model_id == "gpt-5.5"
    assert len(plan.scenarios) == 4
    assert client.responses.request["model"] == "gpt-5.5"
    assert client.responses.request["text_format"] is PlannerPlan


def test_planner_schema_restricts_mechanic_to_the_registry_list():
    """Regression: the model once wrote 'temporary_price_reduction' because the schema allowed any string."""
    import pytest
    from pydantic import ValidationError

    from backend.agent.schemas import PlannerScenario
    from backend.assumptions.assumptions import PROMO_MECHANICS

    schema = PlannerPlan.model_json_schema()
    assert schema["$defs"]["PlannerLever"]["properties"]["mechanic"]["enum"] == PROMO_MECHANICS

    bad = {"name": "x", "sku_levers": [{"sku_id": "Aurora-can_330ml", "lever": {"mechanic": "temporary_price_reduction", "promo_depth_pct": 10}}]}
    with pytest.raises(ValidationError):
        PlannerScenario.model_validate(bad)

    good = {"name": "x", "sku_levers": [{"sku_id": "Aurora-can_330ml", "lever": {"mechanic": "TPR", "promo_depth_pct": 10, "promo_weeks_per_month": 2}}]}
    scenario = PlannerScenario.model_validate(good).to_scenario()
    assert scenario.levers["Aurora-can_330ml"].mechanic == "TPR"


def test_schema_mismatch_is_reported_as_a_clear_configuration_style_error():
    import pytest
    from pydantic import ValidationError

    from backend.agent.openai_llm import OpenAILLMError

    class Broken:
        class responses:  # noqa: N801
            @staticmethod
            def parse(**_):
                PlannerPlan.model_validate({"scenarios": []})

    with pytest.raises(OpenAILLMError, match="did not match the expected schema") as caught:
        OpenAILLM(client=Broken()).plan("goal", {})
    assert isinstance(caught.value.__cause__, ValidationError)


def test_research_and_conjoint_brands_are_restricted_to_the_registry():
    """Regression: the model once set the research brand to 'ALL_500ml', which no SKU has."""
    import pytest
    from pydantic import ValidationError

    from backend.agent.schemas import ConjointAlt, ResearchPlan
    from backend.assumptions.assumptions import BRANDS

    defs = PlannerPlan.model_json_schema()["$defs"]
    assert defs["ResearchPlan"]["properties"]["brand"]["enum"] == BRANDS
    assert defs["ConjointAlt"]["properties"]["brand"]["enum"] == BRANDS
    with pytest.raises(ValidationError):
        ResearchPlan(methodology="Willingness to Pay", brand="ALL_500ml")
    with pytest.raises(ValidationError):
        ConjointAlt(brand="ALL_500ml", pack="pet_500ml", price=10)
    assert ResearchPlan(methodology="Willingness to Pay", brand="Boreal").brand == "Boreal"


def test_planner_sku_ids_are_restricted_to_the_registry():
    import pytest
    from pydantic import ValidationError

    from backend.agent.schemas import SkuLever
    from backend.assumptions.assumptions import SKU_IDS

    assert PlannerPlan.model_json_schema()["$defs"]["SkuLever"]["properties"]["sku_id"]["enum"] == SKU_IDS
    with pytest.raises(ValidationError):
        SkuLever(sku_id="ALL_500ml-pet_500ml", lever={})
    assert SkuLever(sku_id="Aurora-can_330ml", lever={}).lever.mechanic == "none"
