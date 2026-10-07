"""The ten dashboard cases: valid, engine-evaluable, honest about what must be refused, and seeded once."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import db, demo_cases
from backend.api.main import app
from backend.demo_cases import CASES
from backend.engine.batch import evaluate_batch
from backend.model.spec import build_param_draws


@pytest.fixture()
def factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    db.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db, "get_session_factory", lambda: session_factory)
    return session_factory


def test_there_are_ten_distinct_cases_that_fit_the_workspace_limits():
    assert len(CASES) == 10
    assert len({name for name, *_ in CASES}) == 10
    for name, question, scenarios, _ in CASES:
        assert 0 < len(name) <= 120 and 0 < len(question) <= 500
        assert 4 <= len(scenarios) <= 6
        assert len({s.name for s in scenarios}) == len(scenarios), name  # board keys and the brief rely on distinct names


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_each_case_runs_through_the_engine_and_refuses_only_what_it_says(case):
    name, _, scenarios, expected_refused = case
    assert not scenarios[0].levers and not any(scenarios[0].cost_shock.model_dump().values()), "first scenario is the baseline"
    results = evaluate_batch(scenarios, build_param_draws(k=0, seed=42))
    refused = {s.name for s, r in zip(scenarios, results, strict=True) if r.status == "REFUSED"}
    assert refused == expected_refused, name
    assert results[0].status != "REFUSED"
    for s, r in zip(scenarios, results, strict=True):
        assert (r.focal == {}) == (r.status == "REFUSED"), s.name  # refused means no numbers, supported means numbers


def test_the_set_shows_both_winners_and_losers_and_at_least_three_refusals():
    wins = losses = refusals = 0
    for _, _, scenarios, _ in CASES:
        results = evaluate_batch(scenarios, build_param_draws(k=0, seed=42))
        base = results[0].focal["gp"].value
        for r in results[1:]:
            if r.status == "REFUSED":
                refusals += 1
            elif r.focal["gp"].value > base:
                wins += 1
            else:
                losses += 1
    assert wins >= 10 and losses >= 10 and refusals >= 3


def test_seeding_creates_the_cases_once_and_they_load_and_evaluate_over_the_api(factory):
    assert len(demo_cases.seed("owner@example.com")) == 10
    assert demo_cases.seed("owner@example.com") == []  # idempotent
    client = TestClient(app)
    listed = client.get("/workspaces").json()
    assert {w["name"] for w in listed} == {c[0] for c in CASES}
    assert all(w["scenario_count"] >= 4 and w["created_by"] == "owner@example.com" for w in listed)
    first = next(w for w in listed if w["name"] == CASES[0][0])
    saved = client.get(f"/workspaces/{first['id']}/scenarios").json()["scenarios"]
    results = client.post("/scenarios/evaluate", json={"scenarios": saved, "k": 0}).json()
    assert len(results) == len(saved) and results[0]["status"] != "REFUSED"


def test_seeding_without_any_user_fails_clearly(factory):
    with pytest.raises(RuntimeError, match="no active user"):
        demo_cases.seed()
