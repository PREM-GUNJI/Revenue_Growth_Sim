from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import db
from backend.agent.openai_llm import OpenAILLMError
from backend.api import main
from backend.api.main import app


class StubLLM:
    provider, model_id = "openai", "gpt-5.1"
    usage = {"calls": 1, "input_tokens": 900, "cached_input_tokens": 0, "output_tokens": 300}


@pytest.fixture()
def factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(main, "OpenAILLM", StubLLM)
    return session_factory


def run_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> TestClient:
    class Failing:
        def run(self, *_, **__):
            raise error

    monkeypatch.setattr(main, "AgentOrchestrator", Failing)
    return TestClient(app, raise_server_exceptions=False)


def test_unrunnable_plan_is_a_502_with_the_reason_not_a_crash(factory, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    client = run_with(monkeypatch, ValueError("candidate ALL_500ml-pet_500ml is not an observed brand/pack"))
    response = client.post("/agent/run", json={"goal": "Improve margin"})
    assert response.status_code == 502
    assert "ALL_500ml-pet_500ml" in response.json()["detail"] and "cannot run" in response.json()["detail"]


def test_provider_errors_stay_503(factory, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    client = run_with(monkeypatch, OpenAILLMError("OpenAI request failed: RateLimitError (HTTP 429)"))
    response = client.post("/agent/run", json={"goal": "x"})
    assert response.status_code == 503 and "HTTP 429" in response.json()["detail"]


def test_tokens_spent_before_a_failure_are_still_recorded_and_priced(factory, monkeypatch: pytest.MonkeyPatch) -> None:
    client = run_with(monkeypatch, ValueError("boom"))
    client.post("/agent/run", json={"goal": "x", "workspace_id": "w1"})
    with factory() as session:
        row = session.scalar(select(db.AiUsage))
    assert (row.workspace_id, row.input_tokens, row.output_tokens, row.model) == ("w1", 900, 300, "gpt-5.1")
    assert row.cost_usd == pytest.approx(900 * 1.25 / 1e6 + 300 * 10 / 1e6)
