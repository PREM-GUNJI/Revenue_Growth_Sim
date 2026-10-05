"""Scenario request schema (PLAN.md section 6). Pydantic bounds stay loose
so out-of-range requests reach the Phase 5 support envelope and come back
REFUSED, not a 422 — the engine, not validation, is the source of refusal.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from backend.assumptions.assumptions import PROMO_MECHANICS, SKU_IDS

SCHEMA_VERSION = 1


class Lever(BaseModel):
    price_index: float = Field(default=1.0, ge=0.5, le=2.0)
    promo_depth_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    mechanic: str = Field(default="none")
    promo_weeks_per_month: float = Field(default=0.0, ge=0.0, le=4.0)

    @model_validator(mode="after")
    def _validate(self) -> Lever:
        if self.mechanic not in PROMO_MECHANICS:
            raise ValueError(f"unknown mechanic {self.mechanic!r}")
        if self.mechanic == "none" and self.promo_depth_pct != 0.0:
            raise ValueError("mechanic='none' requires promo_depth_pct=0")
        return self


class CostShock(BaseModel):
    aluminium_pct: float = Field(default=0.0, ge=-50.0, le=200.0)
    pet_resin_pct: float = Field(default=0.0, ge=-50.0, le=200.0)
    sugar_pct: float = Field(default=0.0, ge=-50.0, le=200.0)


class Scenario(BaseModel):
    schema_version: int = SCHEMA_VERSION
    name: str = Field(default="", max_length=80)  # display only, never hashed
    levers: dict[str, Lever] = Field(default_factory=dict)  # omitted sku -> baseline Lever()
    cost_shock: CostShock = Field(default_factory=CostShock)

    @model_validator(mode="after")
    def _skus_known(self) -> Scenario:
        unknown = set(self.levers) - set(SKU_IDS)
        if unknown:
            raise ValueError(f"unknown sku ids: {sorted(unknown)}")
        return self
