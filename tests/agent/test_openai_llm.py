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
