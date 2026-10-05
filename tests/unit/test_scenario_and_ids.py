"""Scenario validation, quantization, and hashing invariants (Phase 4)."""

import pytest
from pydantic import ValidationError

from backend.assumptions.assumptions import SKU_IDS
from backend.engine.ids import expand_scenario, scenario_id
from backend.engine.scenario import Lever, Scenario


def test_mechanic_none_requires_zero_depth():
    with pytest.raises(ValidationError):
        Lever(mechanic="none", promo_depth_pct=5.0)


def test_unknown_mechanic_rejected():
    with pytest.raises(ValidationError):
        Lever(mechanic="not_a_real_mechanic")


def test_unknown_sku_rejected():
    with pytest.raises(ValidationError):
        Scenario(levers={"not-a-sku": Lever()})


def test_expand_fills_every_sku():
    expanded = expand_scenario(Scenario(levers={SKU_IDS[0]: Lever(price_index=1.1)}))
    assert set(expanded.levers) == set(SKU_IDS)
    assert expanded.levers[SKU_IDS[0]].price_bp == 1100
    assert expanded.levers[SKU_IDS[1]].price_bp == 1000  # baseline default


def test_scenario_id_ignores_name():
    a = expand_scenario(Scenario(name="Plan A", levers={SKU_IDS[0]: Lever(price_index=1.1)}))
    b = expand_scenario(Scenario(name="Plan B", levers={SKU_IDS[0]: Lever(price_index=1.1)}))
    assert scenario_id(a) == scenario_id(b)


def test_scenario_id_stable_and_sensitive_to_levers():
    base = expand_scenario(Scenario())
    changed = expand_scenario(Scenario(levers={SKU_IDS[0]: Lever(price_index=1.1)}))
    assert scenario_id(base) == scenario_id(expand_scenario(Scenario()))
    assert scenario_id(base) != scenario_id(changed)
