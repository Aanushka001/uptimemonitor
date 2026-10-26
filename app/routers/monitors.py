from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Check, Monitor
from app.schemas import CheckOut, MonitorCreate, MonitorOut, MonitorUpdate
from app.security import require_api_key
from app.services.url_safety import UnsafeURL, validate_target_url

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _validate_url_or_422(url: str) -> None:
    try:
        validate_target_url(url, settings.allow_private_targets)
    except UnsafeURL as exc:
        raise HTTPException(422, str(exc)) from exc


def _get_or_404(db: Session, monitor_id: int) -> Monitor:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Monitor not found")
    return monitor


@router.post("", response_model=MonitorOut, status_code=201, dependencies=[Depends(require_api_key)])
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    _validate_url_or_422(payload.url)
    monitor = Monitor(**payload.model_dump())
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.get("", response_model=list[MonitorOut])
def list_monitors(db: Session = Depends(get_db)):
    return db.execute(select(Monitor).order_by(Monitor.id)).scalars().all()


@router.get("/{monitor_id}", response_model=MonitorOut)
def get_monitor(monitor_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, monitor_id)


@router.patch("/{monitor_id}", response_model=MonitorOut, dependencies=[Depends(require_api_key)])
def update_monitor(monitor_id: int, payload: MonitorUpdate, db: Session = Depends(get_db)):
    monitor = _get_or_404(db, monitor_id)
    changes = payload.model_dump(exclude_unset=True)
    if "url" in changes:
        _validate_url_or_422(changes["url"])
    for field, value in changes.items():
        setattr(monitor, field, value)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=204, dependencies=[Depends(require_api_key)])
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, monitor_id))
    db.commit()
    return Response(status_code=204)


@router.get("/{monitor_id}/checks", response_model=list[CheckOut])
def list_checks(
    monitor_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _get_or_404(db, monitor_id)
    return (
        db.execute(
            select(Check)
            .where(Check.monitor_id == monitor_id)
            .order_by(Check.checked_at.desc(), Check.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
