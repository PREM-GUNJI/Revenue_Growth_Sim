"""Read-only facts for the homepage: database status, workspace counts, latest eval and benchmark results.

Eval pass/fail mirrors the gate in agent_evals/run_evals.py (rates must reach their budget; the
optimality gap must stay under it when it was measured). Report files are read, never written.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from backend import db
from backend.assumptions.assumptions import ASSUMPTIONS
from backend.auth import CurrentUser

ROOT = Path(__file__).resolve().parent.parent
EVALS_FILE = ROOT / "reports" / "agent_evals.json"
BENCH_FILE = ROOT / "reports" / "engine_bench.md"
ADR_DIR = ROOT / "docs" / "spec" / "adr"
RATE_METRICS = ("grounding_rate", "refusal_integrity", "injection_resistance", "label_correctness")
BENCH_ROW = re.compile(r"^\|\s*([\d,]+)\s*\|\s*([\d.]+)\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|\s*(PASS|FAIL)\s*\|", re.M)

router = APIRouter(prefix="/hub", tags=["hub"])


def _modified(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def agent_evals() -> dict[str, Any] | None:
    if not EVALS_FILE.exists():
        return None
    metrics = json.loads(EVALS_FILE.read_text(encoding="utf-8"))["metrics"]
    budgets = metrics["budgets"]
    checks = {name: metrics[name] >= budgets[name] for name in RATE_METRICS}
    gap_measured = metrics.get("optimality_gap_n", 0) > 0
    checks["optimality_gap_median_pct"] = (not gap_measured) or (
        metrics["optimality_gap_median_pct"] <= budgets["optimality_gap_median_pct"])
    return {"tasks": metrics["n_tasks"], "passed": all(checks.values()), "checks": checks,
            "metrics": {name: metrics[name] for name in (*RATE_METRICS, "optimality_gap_median_pct")},
            "budgets": budgets, "report_updated_at": _modified(EVALS_FILE)}


def benchmarks() -> dict[str, Any] | None:
    if not BENCH_FILE.exists():
        return None
    rows = [{"scenarios": int(m.group(1).replace(",", "")), "p95_ms": float(m.group(2)),
             "budget": m.group(3), "result": m.group(4)} for m in BENCH_ROW.finditer(BENCH_FILE.read_text(encoding="utf-8"))]
    return {"rows": rows, "within_budget": sum(r["result"] == "PASS" for r in rows), "total": len(rows),
            "report_updated_at": _modified(BENCH_FILE)}


@router.get("/summary")
def summary(user: CurrentUser) -> dict[str, Any]:
    counts = {"active": 0, "archived": 0}
    factory = db.get_session_factory()
    if factory is not None and db.database_status() == "ok":
        with factory() as session:
            for archived, total in session.execute(select(db.Workspace.archived, func.count()).group_by(db.Workspace.archived)):
                counts["archived" if archived else "active"] = total
    return {
        "database": db.database_status(),
        "workspaces": counts,
        "agent_evals": agent_evals(),
        "benchmarks": benchmarks(),
        "governance": {"assumptions": len(ASSUMPTIONS), "adrs": len(list(ADR_DIR.glob("ADR-*.md")))},
    }
