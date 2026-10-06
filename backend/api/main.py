"""Minimal FastAPI app (Phase 3 adds `/assumptions`; Phase 6 adds the rest).

`GET /assumptions` lists the full catalog for inspection/UI display — it
reads `ASSUMPTIONS` directly rather than through `registry.get()`, since
listing every id isn't a computation that should count toward coverage
(see `tests/assumptions/test_registry.py`'s pending-Phase-4 exclusion set).
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.schemas import AssumptionOut
from backend.assumptions.assumptions import ASSUMPTIONS

app = FastAPI(title="Revenue Growth Scenario Simulator")


@app.get("/assumptions", response_model=list[AssumptionOut])
async def list_assumptions() -> list[AssumptionOut]:
    return [
        AssumptionOut(
            id=a.id,
            label=a.label,
            value=a.value,
            unit=a.unit,
            source=a.source,
            rationale=a.rationale,
            valid_range=a.valid_range,
        )
        for a in sorted(ASSUMPTIONS.values(), key=lambda a: a.id)
    ]
