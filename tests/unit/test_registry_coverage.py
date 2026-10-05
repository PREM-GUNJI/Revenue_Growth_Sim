"""AC-005: every assumption id read by the engine at runtime is registered
with a non-empty rationale and valid_range; an unregistered read fails the
build.

Full 100% coverage of every *registered* assumption isn't claimed: cost
assumptions (A-013..A-017b) have no reader until Phase 4's margin waterfall,
and the qualitative "no X" assumptions (A-018..A-021) are documentation-only
declarations that are never computed. Both sets are named explicitly below so
a future phase that wires one up (and should drop it from the exclusion set)
shows up as a visible diff, not a silently-widening exemption.
"""

import pytest

from backend.assumptions import registry
from backend.assumptions.assumptions import ASSUMPTIONS, Assumption
from backend.assumptions.registry import _validate_rationales
from backend.data.generator import generate
from backend.model.backtest import run_backtest
from backend.model.spec import DRAWABLE_ASSUMPTION_IDS, build_param_draws

COST_IDS_PENDING_PHASE4 = {
    "A-013",
    "A-014a",
    "A-014b",
    "A-014c",
    "A-014d",
    "A-015",
    "A-016",
    "A-017",
    "A-017b",
}
QUALITATIVE_IDS_NEVER_COMPUTED = {"A-018", "A-019", "A-020", "A-021"}


def test_get_returns_assumption_and_tracks_read():
    registry.reset_reads()
    a = registry.get("A-001")
    assert a.id == "A-001"
    assert "A-001" in registry.reads()


def test_get_unregistered_id_raises():
    with pytest.raises(KeyError):
        registry.get("A-999")


def test_validate_rationales_rejects_missing_rationale():
    bad = {
        "A-999": Assumption(
            id="A-999", label="x", value=1, unit=None, source="modelling-choice", rationale=""
        )
    }
    with pytest.raises(ValueError, match="A-999"):
        _validate_rationales(bad)


def test_all_registered_assumptions_have_a_rationale():
    _validate_rationales(ASSUMPTIONS)  # does not raise


def test_every_read_id_has_a_valid_range():
    registry.reset_reads()
    build_param_draws(k=5, seed=1)
    for aid in registry.reads():
        assert ASSUMPTIONS[aid].valid_range is not None


def test_drawable_assumptions_reach_100_percent_coverage_via_model_pipeline():
    registry.reset_reads()
    draws = build_param_draws(k=10, seed=1)
    run_backtest(draws)
    generate(42)

    assert set(DRAWABLE_ASSUMPTION_IDS) <= registry.reads()
    unread = registry.unread_ids()
    assert unread == COST_IDS_PENDING_PHASE4 | QUALITATIVE_IDS_NEVER_COMPUTED
