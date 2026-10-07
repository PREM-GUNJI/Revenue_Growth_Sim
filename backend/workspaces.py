"""Scenario workspaces: named, shared by every signed-in user, with an autosaved scenario list.

Saves carry a `version`; a stale version is rejected with 409 so two people editing the same
workspace cannot silently overwrite each other.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import activity, db, export
from backend.auth import CurrentUser

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
MAX_SCENARIOS = 200
MAX_STATE_BYTES = 2_000_000


def _session() -> Session:
    factory = db.get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="Workspaces are unavailable: DATABASE_URL is not configured")
    return factory()


def _scenario_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if len(value) > MAX_SCENARIOS:
        raise ValueError(f"at most {MAX_SCENARIOS} scenarios per workspace")
    for item in value:
        if not isinstance(item.get("name"), str) or not isinstance(item.get("levers"), dict):
            raise ValueError("each scenario needs a text name and a levers object")
    if len(json.dumps(value)) > MAX_STATE_BYTES:
        raise ValueError("scenario list is too large")
    return value


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    scenarios: list[dict[str, Any]] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    _check = field_validator("scenarios")(lambda cls, v: _scenario_list(v))


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    archived: bool | None = None


class ScenariosIn(BaseModel):
    scenarios: list[dict[str, Any]]
    version: int = Field(ge=1)

    _check = field_validator("scenarios")(lambda cls, v: _scenario_list(v))


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _out(workspace: db.Workspace, state: db.WorkspaceState | None) -> dict[str, Any]:
    return {
        "id": workspace.id, "name": workspace.name, "description": workspace.description,
        "created_by": workspace.created_by, "updated_by": workspace.updated_by,
        "created_at": _iso(workspace.created_at), "updated_at": _iso(workspace.updated_at),
        "archived": workspace.archived,
        "scenario_count": len(state.scenarios or []) if state else 0,
    }


def _get(session: Session, workspace_id: str) -> db.Workspace:
    workspace = session.get(db.Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("")
def list_workspaces(user: CurrentUser, include_archived: bool = False) -> list[dict[str, Any]]:
    with _session() as session:
        query = select(db.Workspace).order_by(db.Workspace.updated_at.desc())
        if not include_archived:
            query = query.where(db.Workspace.archived.is_(False))
        workspaces = list(session.scalars(query))
        states = {s.workspace_id: s for s in session.scalars(
            select(db.WorkspaceState).where(db.WorkspaceState.workspace_id.in_([w.id for w in workspaces])))}
        return [_out(w, states.get(w.id)) for w in workspaces]


@router.post("", status_code=201)
def create_workspace(body: WorkspaceIn, user: CurrentUser) -> dict[str, Any]:
    now = datetime.now(UTC)
    workspace = db.Workspace(id=uuid4().hex, name=body.name, description=body.description.strip(),
                             created_by=user.email, updated_by=user.email, created_at=now, updated_at=now, archived=False)
    state = db.WorkspaceState(workspace_id=workspace.id, scenarios=body.scenarios, version=1, updated_at=now)
    with _session() as session:
        session.add_all([workspace, state])
        session.commit()
        result = _out(workspace, state)
    activity.record(user.email, "workspace.create", workspace.id, {"name": workspace.name})
    return result


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, user: CurrentUser) -> dict[str, Any]:
    with _session() as session:
        workspace = _get(session, workspace_id)
        return _out(workspace, session.get(db.WorkspaceState, workspace_id))


@router.patch("/{workspace_id}")
def update_workspace(workspace_id: str, body: WorkspacePatch, user: CurrentUser) -> dict[str, Any]:
    changes = body.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="name must not be blank")
    with _session() as session:
        workspace = _get(session, workspace_id)
        for key, value in changes.items():
            setattr(workspace, key, value.strip() if isinstance(value, str) else value)
        workspace.updated_by, workspace.updated_at = user.email, datetime.now(UTC)
        session.commit()
        result = _out(workspace, session.get(db.WorkspaceState, workspace_id))
    if "archived" in changes:
        activity.record(user.email, "workspace.archive" if changes["archived"] else "workspace.restore", workspace_id)
    if set(changes) - {"archived"}:
        activity.record(user.email, "workspace.update", workspace_id, {"fields": sorted(set(changes) - {"archived"})})
    return result


@router.get("/{workspace_id}/scenarios")
def get_scenarios(workspace_id: str, user: CurrentUser) -> dict[str, Any]:
    with _session() as session:
        _get(session, workspace_id)
        state = session.get(db.WorkspaceState, workspace_id)
        return {"scenarios": state.scenarios if state else None, "version": state.version if state else 1}


@router.put("/{workspace_id}/scenarios")
def put_scenarios(workspace_id: str, body: ScenariosIn, user: CurrentUser) -> dict[str, Any]:
    now = datetime.now(UTC)
    with _session() as session:
        workspace = _get(session, workspace_id)
        if workspace.archived:
            raise HTTPException(status_code=409, detail="This workspace is archived; restore it to edit")
        state = session.get(db.WorkspaceState, workspace_id)
        if state is None:
            state = db.WorkspaceState(workspace_id=workspace_id, scenarios=None, version=1, updated_at=now)
            session.add(state)
        if state.version != body.version:
            raise HTTPException(status_code=409, detail=f"Changed by {workspace.updated_by} since you opened it; reload to continue")
        state.scenarios, state.version, state.updated_at = body.scenarios, state.version + 1, now
        workspace.updated_by, workspace.updated_at = user.email, now
        session.commit()
        version = state.version
    activity.record(user.email, "workspace.edit", workspace_id, {"scenarios": len(body.scenarios)}, coalesce=True)
    return {"version": version, "scenario_count": len(body.scenarios)}


@router.post("/{workspace_id}/export")
def export_workspace(workspace_id: str, user: CurrentUser) -> Response:
    """A PowerPoint of the workspace's saved scenarios, evaluated by the engine at request time."""
    with _session() as session:
        workspace = _get(session, workspace_id)
        state = session.get(db.WorkspaceState, workspace_id)
        name, saved = workspace.name, list(state.scenarios or []) if state else []
    try:
        scenarios, results = export.evaluate(saved)
    except export.ExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    deck = export.build_deck(name, scenarios, results, user.display_name)
    activity.record(user.email, "workspace.export", workspace_id, {"format": "pptx", "scenarios": len(scenarios)})
    filename = re.sub(r"-+", "-", "".join(c if c.isalnum() or c in "-_" else "-" for c in name)).strip("-")[:60] or "workspace"
    return Response(content=deck, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.pptx"'})


@router.post("/{workspace_id}/brief")
def brief_workspace(workspace_id: str, user: CurrentUser, trace_id: str | None = None) -> Response:
    """A one-page labelled brief (HTML, print to PDF) of the saved scenarios."""
    with _session() as session:
        workspace = _get(session, workspace_id)
        state = session.get(db.WorkspaceState, workspace_id)
        name, saved = workspace.name, list(state.scenarios or []) if state else []
    try:
        scenarios, results = export.evaluate(saved)
    except export.ExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    activity.record(user.email, "workspace.export", workspace_id, {"format": "brief", "scenarios": len(scenarios)})
    return Response(content=export.build_brief(name, scenarios, results, user.display_name, trace_id), media_type="text/html")
