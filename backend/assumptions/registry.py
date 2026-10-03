"""Read-tracking access layer over `ASSUMPTIONS` (PLAN.md section 3, Phase 3).

CLAUDE.md: "Every number the engine uses comes from the assumptions
registry (`registry.get("A-xxx")`). No magic constants elsewhere." This
module is that single door: code that needs an assumption's value calls
`get(id)`, never imports the `Assumption` object just to read `.value`.
Every call is recorded, so `coverage()`/`unread_ids()` can prove which
assumptions are actually wired into a computation and which aren't yet.
"""

from __future__ import annotations

from backend.assumptions.assumptions import ASSUMPTIONS, Assumption


def _validate_rationales(assumptions: dict[str, Assumption]) -> None:
    for aid, a in assumptions.items():
        if not a.rationale or not a.rationale.strip():
            raise ValueError(f"assumption {aid} has no rationale")


_validate_rationales(ASSUMPTIONS)  # build fails at import time if one is missing

_reads: set[str] = set()


def get(assumption_id: str) -> Assumption:
    """Look up a registered assumption, recording the read for coverage checks."""
    assumption = ASSUMPTIONS[assumption_id]  # KeyError: unregistered id, fails loudly
    _reads.add(assumption_id)
    return assumption


def reads() -> set[str]:
    return set(_reads)


def reset_reads() -> None:
    _reads.clear()


def unread_ids() -> set[str]:
    return set(ASSUMPTIONS) - _reads


def coverage() -> float:
    if not ASSUMPTIONS:
        return 1.0
    return len(_reads & ASSUMPTIONS.keys()) / len(ASSUMPTIONS)
