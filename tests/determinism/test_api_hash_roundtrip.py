"""AC-014/015: API hashing is stable and exported scenarios reproduce."""

import subprocess
import sys

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.assumptions.assumptions import SKU_IDS
from backend.engine.scenario import Lever, Scenario

client = TestClient(app)


def test_result_hash_is_stable_across_100_batch_repeats():
    scenario = Scenario(levers={SKU_IDS[0]: Lever(price_index=1.0)})
    body = {"scenarios": [scenario.model_dump(mode="json")] * 100, "k": 0, "seed": 19}
    response = client.post("/scenarios/evaluate", json=body)
    assert response.status_code == 200
    hashes = {item["result_hash"] for item in response.json()}
    assert len(hashes) == 1


def test_result_hash_is_stable_across_process_restarts():
    script = (
        "from backend.engine.batch import evaluate_one; "
        "from backend.engine.scenario import Scenario; "
        "from backend.model.spec import build_param_draws; "
        "print(evaluate_one(Scenario(), build_param_draws(k=0, seed=19)).result_hash)"
    )
    values = [
        subprocess.check_output([sys.executable, "-c", script], text=True).strip()
        for _ in range(2)
    ]
    assert values[0] == values[1]


def test_export_import_recomputes_identical_ids_and_hash():
    scenario = Scenario(levers={SKU_IDS[0]: Lever(price_index=1.0)})
    exported = client.post("/scenarios/export", json={
        "scenario": scenario.model_dump(mode="json"), "k": 0, "seed": 19
    })
    assert exported.status_code == 200
    payload = exported.json()
    imported = client.post("/scenarios/import", json=payload)
    assert imported.status_code == 200
    assert imported.json()["scenario_id"] == payload["scenario_id"]
    assert imported.json()["result_hash"] == payload["result_hash"]


def test_import_rejects_tampered_result_hash():
    scenario = Scenario()
    payload = client.post("/scenarios/export", json={
        "scenario": scenario.model_dump(mode="json"), "k": 0, "seed": 19
    }).json()
    payload["result_hash"] = "0" * 64
    assert client.post("/scenarios/import", json=payload).status_code == 422
