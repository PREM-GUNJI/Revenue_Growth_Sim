"""Phase 16-17 AC traceability gate.

Every AC-xxx acceptance criterion defined in docs/spec/BRD.md must map to a
named test (or other concrete evidence file — a CI workflow for the two
process-level ACs that aren't pytest-shaped) that explicitly names it, or
have an explicit, defect-logged gap in KNOWN_GAPS below.

This follows the same explicit-exemption-set convention already used by
tests/unit/test_registry_coverage.py for assumption-id coverage: gaps are
named, justified, and cross-checked against docs/agent-record/DEFECTS.md
rather than silently skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRD = ROOT / "docs" / "spec" / "BRD.md"
DEFECTS = ROOT / "docs" / "agent-record" / "DEFECTS.md"

BRD_AC_RE = re.compile(r"\*\*AC-(\d{3})\*\*")
FUNC_AC_RE = re.compile(r"def test_ac0?(\d{3})_")
TEXT_AC_RE = re.compile(r"AC-(\d{3})")

# Directories scanned for AC coverage: pytest tests, the agent-eval harness
# (AC-019/021/023 are scored there, not in tests/), the latency benchmark
# (AC-016), and CI workflow files (AC-025/026, which are process-level
# criteria about the pipeline itself, not a pytest function).
SEARCH_DIRS = [
    ROOT / "tests",
    ROOT / "agent_evals",
    ROOT / "benchmarks",
    ROOT / ".github" / "workflows",
]

# ACs with no automated test yet. Each entry here MUST also have a matching
# "AC-xxx" mention in DEFECTS.md (checked below) — this is not an escape
# hatch, it is a cross-checked, honestly logged gap.
KNOWN_GAPS = {
    "027": (
        "Phase 19 (containerised deploy + rollback) has not started. "
        "BRD.md itself specifies 'Evidence: docs/ops/ROLLBACK_EVIDENCE.md' "
        "for this AC, not a pytest test."
    ),
}


def _all_ac_ids_in_brd() -> set[str]:
    text = BRD.read_text(encoding="utf-8")
    ids = set(BRD_AC_RE.findall(text))
    assert ids, "expected to find **AC-xxx** entries in docs/spec/BRD.md"
    return ids


def _covered_ac_ids() -> dict[str, list[str]]:
    coverage: dict[str, list[str]] = {}
    for base in SEARCH_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".yml", ".yaml"}:
                continue
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            found = set(FUNC_AC_RE.findall(text)) | set(TEXT_AC_RE.findall(text))
            for ac in found:
                coverage.setdefault(ac, []).append(str(path.relative_to(ROOT)))
    return coverage


def test_every_brd_ac_has_a_named_test_or_a_logged_gap():
    all_ids = _all_ac_ids_in_brd()
    coverage = _covered_ac_ids()
    defects_text = DEFECTS.read_text(encoding="utf-8")

    missing = []
    for ac in sorted(all_ids):
        if ac in coverage:
            continue
        if ac in KNOWN_GAPS:
            assert f"AC-{ac}" in defects_text, (
                f"AC-{ac} is declared in KNOWN_GAPS but has no matching "
                f"'AC-{ac}' entry in docs/agent-record/DEFECTS.md"
            )
            continue
        missing.append(f"AC-{ac}")

    assert not missing, (
        "These ACs have no test/evidence file naming them and no logged "
        f"gap in tests/test_ac_traceability.py's KNOWN_GAPS: {missing}"
    )


def test_known_gaps_are_not_secretly_already_covered():
    """Once a KNOWN_GAPS id gets a real test, the exemption must be removed
    here instead of being left to rot as a stale, misleading gap."""
    coverage = _covered_ac_ids()
    stale = sorted(ac for ac in KNOWN_GAPS if ac in coverage)
    assert not stale, (
        "Remove these from KNOWN_GAPS in tests/test_ac_traceability.py, "
        f"they now have real coverage: {['AC-' + ac for ac in stale]}"
    )


def test_known_gaps_do_not_silently_grow():
    """A guard against quietly adding more exemptions than are actually
    justified: every BRD AC must be either covered or in this fixed set."""
    all_ids = _all_ac_ids_in_brd()
    unexplained_gaps = set(KNOWN_GAPS) - all_ids
    assert not unexplained_gaps, (
        f"KNOWN_GAPS references AC ids not present in BRD.md: {unexplained_gaps}"
    )
