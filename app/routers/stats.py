from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Monitor
from app.services.stats import WINDOWS, fetch_stats

router = APIRouter(tags=["stats"])


@router.get("/monitors/{monitor_id}/stats")
def monitor_stats(
    monitor_id: int,
    window: str = Query(default="24h", description=f"One of: {', '.join(WINDOWS)}"),
    db: Session = Depends(get_db),
):
    if window not in WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(WINDOWS)}")
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(404, "Monitor not found")
    return fetch_stats(db, window, monitor_id)[0]
