"""Database side effects for checks and incidents."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Alert, Check, Incident, Monitor
from app.services import alerts
from app.services.checker import CheckResult
from app.services.decision import NOOP, OPEN, RESOLVE, decide


def recent_outcomes(db: Session, monitor_id: int, limit: int) -> list[bool]:
    """Latest check outcomes for a monitor, newest first."""
    rows = db.execute(
        select(Check.is_success)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .limit(limit)
    ).all()
    return [row[0] for row in rows]


def get_open_incident(db: Session, monitor_id: int) -> Incident | None:
    return db.execute(
        select(Incident).where(Incident.monitor_id == monitor_id, Incident.resolved_at.is_(None))
    ).scalar_one_or_none()


def record_result(db: Session, monitor: Monitor, result: CheckResult) -> str:
    """Store a check, apply the incident rules, send alerts. Returns the action taken."""
    db.add(
        Check(
            monitor_id=monitor.id,
            status_code=result.status_code,
            response_ms=result.response_ms,
            is_success=result.is_success,
            error=result.error,
        )
    )
    db.execute(
        Monitor.__table__.update().where(Monitor.id == monitor.id).values(last_checked_at=func.now())
    )
    db.flush()

    outcomes = recent_outcomes(db, monitor.id, monitor.failure_threshold)
    open_incident = get_open_incident(db, monitor.id)
    action = decide(outcomes, open_incident is not None, monitor.failure_threshold)

    pending_alert: tuple[Incident, str, str] | None = None

    if action == OPEN:
        incident = Incident(monitor_id=monitor.id, last_error=result.error)
        try:
            with db.begin_nested():
                db.add(incident)
                db.flush()
        except IntegrityError:
            # The unique index says an incident is already open: treat as no-op.
            action = NOOP
        else:
            pending_alert = (
                incident,
                "down",
                alerts.down_message(monitor.name, monitor.url, result.error),
            )
    elif action == RESOLVE and open_incident is not None:
        open_incident.resolved_at = func.now()
        pending_alert = (
            open_incident,
            "recovered",
            alerts.recovered_message(monitor.name, monitor.url),
        )

    db.commit()

    if pending_alert:
        incident, kind, text = pending_alert
        delivered = alerts.send_telegram(text)
        db.add(Alert(incident_id=incident.id, kind=kind, delivered=delivered))
        db.commit()

    return action
