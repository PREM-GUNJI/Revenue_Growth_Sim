from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import ai_pricing, audit, db
from backend.agent.openai_llm import OpenAILLM
from backend.agent.schemas import PlannerPlan
from backend.api.main import app

TRACE = "a" * 32


def usage(inp: int, cached: int, out: int):
    return SimpleNamespace(input_tokens=inp, output_tokens=out, input_tokens_details=SimpleNamespace(cached_tokens=cached))


class FakeClient:
    """Stands in for the OpenAI client; each call returns a plan and reports the next usage object."""

    def __init__(self, usages):
        self._usages = list(usages)
        self.responses = SimpleNamespace(parse=self._parse)

    def _parse(self, **_):
        return SimpleNamespace(output_parsed=PlannerPlan(scenarios=[{"name": n} for n in "ABCD"]), usage=self._usages.pop(0))


@pytest.fixture()
def factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: session_factory)
    return session_factory


@pytest.fixture()
def client(factory) -> TestClient:  # noqa: ARG001
    return TestClient(app)


# ---- pricing ---------------------------------------------------------------------------------

def test_cost_uses_cached_rate_for_the_cached_part_only() -> None:
    # 1M input of which 400k cached, 100k output: 600k*$5 + 400k*$0.50 + 100k*$30 per 1M
    assert ai_pricing.cost_usd("gpt-5.5", 1_000_000, 400_000, 100_000) == pytest.approx(3.0 + 0.2 + 3.0)


def test_cost_for_a_small_run_and_edge_values() -> None:
    assert ai_pricing.cost_usd("gpt-5.5", 2_000, 0, 500) == pytest.approx(0.01 + 0.015)
    assert ai_pricing.cost_usd("gpt-5.5", 0, 0, 0) == 0
    assert ai_pricing.cost_usd("gpt-5.5", 100, 999, 0) == pytest.approx(100 * 0.50 / 1e6)  # cached capped at input


def test_gpt_5_1_is_priced_from_its_own_rates() -> None:
    assert ai_pricing.cost_usd("gpt-5.1", 1_000_000, 0, 0) == pytest.approx(1.25)
    assert ai_pricing.cost_usd("gpt-5.1", 0, 0, 1_000_000) == pytest.approx(10.00)
    assert ai_pricing.cost_usd("gpt-5.1", 1_000_000, 1_000_000, 0) == pytest.approx(0.125)


def test_unknown_model_has_no_cost_rather_than_a_guess() -> None:
    assert ai_pricing.cost_usd("some-future-model", 1000, 0, 1000) is None
    assert ai_pricing.rate_table()["source"].startswith("https://developers.openai.com")


# ---- usage capture ---------------------------------------------------------------------------

def test_usage_is_summed_across_every_call() -> None:
    llm = OpenAILLM(client=FakeClient([usage(1000, 200, 300), usage(500, 0, 100)]))
    llm.plan("goal", {})
    llm.plan("goal", {})
    assert llm.usage == {"calls": 2, "input_tokens": 1500, "cached_input_tokens": 200, "output_tokens": 400}


def test_response_without_usage_counts_nothing() -> None:
    llm = OpenAILLM(client=FakeClient([None]))
    llm.plan("goal", {})
    assert llm.usage["input_tokens"] == 0 and llm.usage["calls"] == 0


def test_record_agent_usage_writes_priced_row_and_activity(factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.5")  # the model comes from the environment; pin it so the rate is known
    llm = OpenAILLM(client=FakeClient([usage(2000, 0, 500)]))
    llm.plan("goal", {})
    audit.record_agent_usage("a@c5i.ai", "ws1", TRACE, llm, "Compare a price rise " + "x" * 400)
    with factory() as session:
        row = session.scalar(select(db.AiUsage))
        log = session.scalar(select(db.ActivityLog))
    assert (row.model, row.input_tokens, row.output_tokens, row.rate_version) == ("gpt-5.5", 2000, 500, ai_pricing.RATE_VERSION)
    assert row.cost_usd == pytest.approx(0.025)
    assert log.action == "agent.run" and log.detail["trace_id"] == TRACE and len(log.detail["goal"]) == 200


def test_scripted_llm_run_is_recorded_as_zero_tokens(factory) -> None:
    scripted = SimpleNamespace(model_id="scripted")
    audit.record_agent_usage("a@c5i.ai", None, TRACE, scripted, "goal")
    with factory() as session:
        row = session.scalar(select(db.AiUsage))
    assert (row.provider, row.input_tokens, row.output_tokens, row.cost_usd) == ("scripted", 0, 0, None)


# ---- endpoints -------------------------------------------------------------------------------

def seed(factory) -> None:
    with factory() as session:
        session.add_all([db.Workspace(id="w1", name="Pricing", created_by="x", updated_by="x"),
                         db.Workspace(id="w2", name="Promo", created_by="x", updated_by="x")])
        session.add_all([
            db.AiUsage(user_email="a@c5i.ai", workspace_id="w1", trace_id=TRACE, provider="openai", model="gpt-5.5",
                       input_tokens=2000, output_tokens=500, cost_usd=0.025, rate_version="v"),
            db.AiUsage(user_email="b@c5i.ai", workspace_id="w1", trace_id="b" * 32, provider="openai", model="gpt-5.5",
                       input_tokens=1000, output_tokens=100, cost_usd=0.008, rate_version="v"),
            db.AiUsage(user_email="a@c5i.ai", workspace_id="w2", trace_id="c" * 32, provider="openai", model="other",
                       input_tokens=700, output_tokens=70, cost_usd=None, rate_version="v")])
        session.commit()


def test_ai_usage_totals_and_grouping(client: TestClient, factory) -> None:
    seed(factory)
    body = client.get("/audit/ai-usage").json()
    assert body["totals"]["runs"] == 3 and body["totals"]["input_tokens"] == 3700 and body["totals"]["output_tokens"] == 670
    assert body["totals"]["cost_usd"] == pytest.approx(0.033) and body["totals"]["unpriced_runs"] == 1
    pricing = next(w for w in body["by_workspace"] if w["key"] == "w1")
    assert pricing["name"] == "Pricing" and pricing["runs"] == 2 and pricing["cost_usd"] == pytest.approx(0.033)
    promo = next(w for w in body["by_workspace"] if w["key"] == "w2")
    assert promo["cost_usd"] is None and promo["unpriced_runs"] == 1  # shown as unpriced, never as $0
    assert {u["key"] for u in body["by_user"]} == {"a@c5i.ai", "b@c5i.ai"}
    only = client.get("/audit/ai-usage?workspace_id=w2").json()
    assert only["totals"]["runs"] == 1 and body["rates"]["models"]["gpt-5.5"]["output"] == 30.0


def test_audit_log_filters_and_pages(client: TestClient, factory) -> None:
    for action, who in [("auth.login", "a@c5i.ai"), ("workspace.create", "a@c5i.ai"), ("auth.login", "b@c5i.ai")]:
        audit.activity.record(who, action)
    everything = client.get("/audit/log").json()
    assert everything["total"] == 3 and "auth.login" in everything["actions"]
    assert [i["user_email"] for i in client.get("/audit/log?action=auth.login").json()["items"]] == ["b@c5i.ai", "a@c5i.ai"]
    assert client.get("/audit/log?user_email=A@C5I.AI").json()["total"] == 2
    page = client.get("/audit/log?limit=1&offset=2").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert client.get("/audit/log?limit=0").status_code == 422 and client.get("/audit/log?limit=9999").status_code == 422


# ---- agent run history -----------------------------------------------------------------------

def write_trace(directory, trace_id: str = TRACE) -> None:
    lines = [{"type": "header", "model_id": "gpt-5.5", "prompt_version_hash": "h", "temperature": 0},
             {"type": "tool", "call_id": "call_0001", "name": "evaluate_scenarios", "arguments": {"secret": "big"}, "result": {"big": 1}, "result_hash": "rh"},
             {"type": "final", "answer": {"summary": "ok"}, "audit": {"issues": []}}]
    (directory / f"{trace_id}.jsonl").write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")


def test_run_detail_returns_trimmed_trace(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TRACE_DIR", str(tmp_path))
    write_trace(tmp_path)
    body = client.get(f"/agent/runs/{TRACE}").json()
    assert body["model_id"] == "gpt-5.5" and body["answer"] == {"summary": "ok"}
    assert body["tool_calls"] == [{"call_id": "call_0001", "name": "evaluate_scenarios", "result_hash": "rh"}]  # no raw results


@pytest.mark.parametrize("bad", ["..%2F..%2Fpyproject", "..", "A" * 32, "a" * 31, "a" * 33, "%2e%2e%2f" + "a" * 20, "a" * 32 + ".jsonl"])
def test_run_detail_rejects_anything_but_a_32_hex_id(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv("AGENT_TRACE_DIR", str(tmp_path))
    (tmp_path.parent / "pyproject.jsonl").write_text("{}", encoding="utf-8")
    assert client.get(f"/agent/runs/{bad}").status_code == 404


def test_unknown_but_valid_id_is_404(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TRACE_DIR", str(tmp_path))
    assert client.get(f"/agent/runs/{'d' * 32}").status_code == 404


def test_runs_list_joins_tokens_and_workspace(client: TestClient, factory) -> None:
    seed(factory)
    audit.activity.record("a@c5i.ai", "agent.run", "w1", {"trace_id": TRACE, "goal": "Compare options"})
    runs = client.get("/agent/runs").json()
    assert runs[0]["goal"] == "Compare options" and runs[0]["workspace_name"] == "Pricing"
    assert runs[0]["input_tokens"] == 2000 and runs[0]["cost_usd"] == pytest.approx(0.025)
    assert client.get("/agent/runs?workspace_id=w2").json() == []


@pytest.mark.real_auth
def test_all_audit_routes_require_sign_in(factory) -> None:  # noqa: ARG001
    anon = TestClient(app)
    for path in ("/audit/log", "/audit/ai-usage", "/agent/runs", f"/agent/runs/{TRACE}"):
        assert anon.get(path).status_code == 401, path
    assert anon.post("/agent/run", json={"goal": "x"}).status_code == 401
