"""Best-effort audit trail. Records who did what; never scenario contents, passwords or tokens."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from backend import db

log = logging.getLogger(__name__)
COALESCE_WINDOW = timedelta(minutes=15)


def record(user_email: str, action: str, workspace_id: str | None = None,
           detail: dict[str, Any] | None = None, *, coalesce: bool = False) -> None:
    """Append an audit row. With `coalesce`, repeats by the same user on the same workspace within
    15 minutes update the earlier row instead (used for autosave so editing is one entry, not hundreds).
    A failure here is logged but never breaks the request that triggered it."""
    factory = db.get_session_factory()
    if factory is None:
        return
    try:
        with factory() as session:
            now = datetime.now(UTC)
            if coalesce:
                latest = session.scalar(
                    select(db.ActivityLog)
                    .where(db.ActivityLog.user_email == user_email, db.ActivityLog.action == action,
                           db.ActivityLog.workspace_id == workspace_id)
                    .order_by(db.ActivityLog.at.desc()).limit(1))
                if latest is not None:
                    seen = latest.at if latest.at.tzinfo else latest.at.replace(tzinfo=UTC)
                    if now - seen < COALESCE_WINDOW:
                        latest.at = now
                        session.commit()
                        return
            session.add(db.ActivityLog(at=now, user_email=user_email, action=action,
                                       workspace_id=workspace_id, detail=detail))
            session.commit()
    except Exception:  # noqa: BLE001 - auditing must not take the app down
        log.exception("could not record activity %s", action)
