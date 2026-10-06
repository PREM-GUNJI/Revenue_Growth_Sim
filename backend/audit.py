"""Audit page backend: the activity log, AI token usage and cost, and read-only agent run history.

Everything here is read-only except `record_agent_usage`, which the agent endpoint calls once per run.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import activity, ai_pricing, db
from backend.auth import CurrentUser

router = APIRouter(tags=["audit"])
TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
PAGE_MAX = 200


def trace_dir() -> Path:
    import os

    return Path(os.getenv("AGENT_TRACE_DIR", "data/traces"))


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _session() -> Session:
    factory = db.get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="The audit trail is unavailable: DATABASE_URL is not configured")
    return factory()


def _window(start: datetime | None, end: datetime | None) -> tuple[datetime | None, datetime | None]:
    # `end` is a calendar day in the UI; make it inclusive of that whole day.
    return start, (end + timedelta(days=1) if end and end.hour == end.minute == end.second == 0 else end)


def record_agent_usage(user_email: str, workspace_id: str | None, trace_id: str, llm: Any, goal: str) -> None:
    """Write one ai_usage row and one activity row for an agent run. Never raises."""
    factory = db.get_session_factory()
    if factory is None:
        return
    usage = getattr(llm, "usage", None) or {}
    model = getattr(llm, "model_id", "unknown")
    inp, cached, out = (int(usage.get(k, 0)) for k in ("input_tokens", "cached_input_tokens", "output_tokens"))
    try:
        with factory() as session:
            session.add(db.AiUsage(
                user_email=user_email, workspace_id=workspace_id, trace_id=trace_id,
                provider=getattr(llm, "provider", "scripted"), model=model,
                input_tokens=inp, cached_input_tokens=cached, output_tokens=out,
                cost_usd=ai_pricing.cost_usd(model, inp, cached, out), rate_version=ai_pricing.RATE_VERSION))
            session.commit()
    except Exception:  # noqa: BLE001 - usage bookkeeping must not break the run
        import logging

        logging.getLogger(__name__).exception("could not record AI usage for %s", trace_id)
    activity.record(user_email, "agent.run", workspace_id, {"trace_id": trace_id, "goal": goal[:200]})


@router.get("/audit/log")
def audit_log(user: CurrentUser, user_email: str | None = None, action: str | None = None,
              workspace_id: str | None = None, start: datetime | None = None, end: datetime | None = None,
              limit: int = Query(50, ge=1, le=PAGE_MAX), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    start, end = _window(start, end)
    conditions = []
    if user_email:
        conditions.append(db.ActivityLog.user_email == user_email.strip().lower())
    if action:
        conditions.append(db.ActivityLog.action == action)
    if workspace_id:
        conditions.append(db.ActivityLog.workspace_id == workspace_id)
    if start:
        conditions.append(db.ActivityLog.at >= start)
    if end:
        conditions.append(db.ActivityLog.at < end)
    with _session() as session:
        total = session.scalar(select(func.count()).select_from(db.ActivityLog).where(*conditions)) or 0
        rows = session.scalars(select(db.ActivityLog).where(*conditions).order_by(db.ActivityLog.at.desc(), db.ActivityLog.id.desc())
                               .limit(limit).offset(offset))
        names = {w.id: w.name for w in session.scalars(select(db.Workspace))}
        return {"total": total, "limit": limit, "offset": offset, "actions": sorted(set(session.scalars(select(db.ActivityLog.action).distinct()))),
                "items": [{"id": r.id, "at": _iso(r.at), "user_email": r.user_email, "action": r.action, "workspace_id": r.workspace_id,
                           "workspace_name": names.get(r.workspace_id) if r.workspace_id else None, "detail": r.detail} for r in rows]}


def _bucket(rows: list[db.AiUsage]) -> dict[str, Any]:
    priced = [r.cost_usd for r in rows if r.cost_usd is not None]
    return {"runs": len(rows), "input_tokens": sum(r.input_tokens for r in rows), "cached_input_tokens": sum(r.cached_input_tokens for r in rows),
            "output_tokens": sum(r.output_tokens for r in rows), "cost_usd": round(sum(priced), 6) if priced else None,
            "unpriced_runs": len(rows) - len(priced)}


@router.get("/audit/ai-usage")
def ai_usage(user: CurrentUser, workspace_id: str | None = None, start: datetime | None = None,
             end: datetime | None = None) -> dict[str, Any]:
    start, end = _window(start, end)
    conditions = []
    if workspace_id:
        conditions.append(db.AiUsage.workspace_id == workspace_id)
    if start:
        conditions.append(db.AiUsage.at >= start)
    if end:
        conditions.append(db.AiUsage.at < end)
    with _session() as session:
        rows = list(session.scalars(select(db.AiUsage).where(*conditions).order_by(db.AiUsage.at.desc())))
        names = {w.id: w.name for w in session.scalars(select(db.Workspace))}

    def grouped(key) -> list[dict[str, Any]]:
        groups: dict[Any, list[db.AiUsage]] = {}
        for row in rows:
            groups.setdefault(key(row), []).append(row)
        return [{"key": k, **_bucket(v)} for k, v in sorted(groups.items(), key=lambda kv: -(sum(r.cost_usd or 0 for r in kv[1])))]

    by_workspace = grouped(lambda r: r.workspace_id)
    for item in by_workspace:
        item["name"] = names.get(item["key"], "No workspace") if item["key"] else "No workspace"
    return {
        "totals": _bucket(rows), "by_workspace": by_workspace,
        "by_user": grouped(lambda r: r.user_email), "by_model": grouped(lambda r: f"{r.provider}:{r.model}"),
        "recent": [{"at": _iso(r.at), "user_email": r.user_email, "workspace_id": r.workspace_id,
                    "workspace_name": names.get(r.workspace_id) if r.workspace_id else None, "trace_id": r.trace_id,
                    "model": r.model, "input_tokens": r.input_tokens, "cached_input_tokens": r.cached_input_tokens,
                    "output_tokens": r.output_tokens, "cost_usd": r.cost_usd} for r in rows[:100]],
        "rates": ai_pricing.rate_table(),
    }


@router.get("/agent/runs")
def agent_runs(user: CurrentUser, workspace_id: str | None = None, limit: int = Query(50, ge=1, le=PAGE_MAX)) -> list[dict[str, Any]]:
    """Past agent runs, newest first, from the audit trail (goal, who, where, tokens, cost)."""
    with _session() as session:
        query = select(db.ActivityLog).where(db.ActivityLog.action == "agent.run").order_by(db.ActivityLog.at.desc()).limit(limit)
        if workspace_id:
            query = query.where(db.ActivityLog.workspace_id == workspace_id)
        logs = list(session.scalars(query))
        usage = {u.trace_id: u for u in session.scalars(select(db.AiUsage).where(db.AiUsage.trace_id.in_(
            [(r.detail or {}).get("trace_id") for r in logs])))}
        names = {w.id: w.name for w in session.scalars(select(db.Workspace))}
    out = []
    for row in logs:
        detail = row.detail or {}
        tokens = usage.get(detail.get("trace_id"))
        out.append({"trace_id": detail.get("trace_id"), "goal": detail.get("goal", ""), "at": _iso(row.at), "user_email": row.user_email,
                    "workspace_id": row.workspace_id, "workspace_name": names.get(row.workspace_id) if row.workspace_id else None,
                    "input_tokens": tokens.input_tokens if tokens else None, "output_tokens": tokens.output_tokens if tokens else None,
                    "cost_usd": tokens.cost_usd if tokens else None})
    return out


@router.get("/agent/runs/{trace_id}")
def agent_run_detail(trace_id: str, user: CurrentUser) -> dict[str, Any]:
    """One saved trace: tool calls (names, ids, hashes) and the final labelled answer with its audit verdict."""
    if not TRACE_ID.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="Trace not found")
    base = trace_dir().resolve()
    path = (base / f"{trace_id}.jsonl").resolve()
    if path.parent != base or not path.is_file():
        raise HTTPException(status_code=404, detail="Trace not found")
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = next((e for e in entries if e.get("type") == "header"), {})
    final = next((e for e in reversed(entries) if e.get("type") == "final"), None)
    return {
        "trace_id": trace_id,
        "model_id": header.get("model_id"), "prompt_version_hash": header.get("prompt_version_hash"),
        "tool_calls": [{"call_id": e.get("call_id"), "name": e.get("name"), "result_hash": e.get("result_hash")}
                       for e in entries if e.get("type") == "tool"],
        "answer": final.get("answer") if final else None, "audit": final.get("audit") if final else None,
    }
