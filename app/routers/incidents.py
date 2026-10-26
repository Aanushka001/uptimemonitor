from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Incident, Monitor
from app.schemas import IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: Literal["open", "resolved", "all"] = "all",
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = (
        select(Incident, Monitor.name)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .order_by(Incident.started_at.desc())
        .limit(limit)
    )
    if status == "open":
        query = query.where(Incident.resolved_at.is_(None))
    elif status == "resolved":
        query = query.where(Incident.resolved_at.is_not(None))

    return [
        IncidentOut(
            id=incident.id,
            monitor_id=incident.monitor_id,
            monitor_name=name,
            started_at=incident.started_at,
            resolved_at=incident.resolved_at,
            last_error=incident.last_error,
        )
        for incident, name in db.execute(query).all()
    ]
