import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import Alert, Check, Incident, Monitor
from app.services.checker import CheckResult
from app.services.incidents import record_result
from app.services.stats import fetch_stats
from app.worker import find_due_monitors

FAIL = CheckResult(500, 120, False, "HTTP 500")
OK = CheckResult(200, 100, True, None)


def make_monitor(db, **kwargs):
    monitor = Monitor(name="Example", url="https://8.8.8.8/", **kwargs)
    db.add(monitor)
    db.commit()
    return monitor


def test_incident_opens_after_threshold_and_resolves_on_recovery(db):
    monitor = make_monitor(db, failure_threshold=3)

    assert record_result(db, monitor, FAIL) == "NOOP"
    assert record_result(db, monitor, FAIL) == "NOOP"
    assert db.execute(select(Incident)).scalars().all() == []

    assert record_result(db, monitor, FAIL) == "OPEN"
    incident = db.execute(select(Incident)).scalar_one()
    assert incident.resolved_at is None and incident.last_error == "HTTP 500"

    assert record_result(db, monitor, FAIL) == "NOOP"
    assert len(db.execute(select(Incident)).scalars().all()) == 1

    assert record_result(db, monitor, OK) == "RESOLVE"
    db.expire_all()
    assert db.execute(select(Incident)).scalar_one().resolved_at is not None

    kinds = [a.kind for a in db.execute(select(Alert).order_by(Alert.id)).scalars()]
    assert kinds == ["down", "recovered"]
    assert len(db.execute(select(Check)).scalars().all()) == 5


def test_single_blip_never_opens_incident(db):
    monitor = make_monitor(db, failure_threshold=3)
    for result in (OK, FAIL, OK, FAIL, OK):
        record_result(db, monitor, result)
    assert db.execute(select(Incident)).scalars().all() == []


def test_database_rejects_two_open_incidents_for_one_monitor(db):
    monitor = make_monitor(db)
    db.add(Incident(monitor_id=monitor.id))
    db.commit()
    db.add(Incident(monitor_id=monitor.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_resolved_incident_allows_a_new_one(db):
    monitor = make_monitor(db, failure_threshold=1)
    record_result(db, monitor, FAIL)
    record_result(db, monitor, OK)
    record_result(db, monitor, FAIL)
    assert len(db.execute(select(Incident)).scalars().all()) == 2


def test_new_monitor_is_due_then_not_due_after_check(db):
    monitor = make_monitor(db, interval_seconds=60)
    assert [m.id for m in find_due_monitors(db)] == [monitor.id]
    record_result(db, monitor, OK)
    assert find_due_monitors(db) == []


def test_paused_monitor_is_never_due(db):
    make_monitor(db, is_active=False)
    assert find_due_monitors(db) == []


def test_stats_sql_computes_uptime_and_latency(db):
    monitor = make_monitor(db)
    pending = Monitor(name="Never checked", url="https://8.8.4.4/")
    db.add(pending)
    for ms, ok in [(100, True), (200, True), (300, True), (None, False)]:
        db.add(Check(monitor_id=monitor.id, response_ms=ms, is_success=ok))
    db.commit()

    stats = {s["name"]: s for s in fetch_stats(db, "24h")}
    example = stats["Example"]
    assert example["total_checks"] == 4
    assert example["uptime_pct"] == 75.0
    assert example["avg_ms"] == 200.0
    assert example["p95_ms"] is not None
    assert example["status"] == "up"
    assert stats["Never checked"]["status"] == "pending"
    assert stats["Never checked"]["uptime_pct"] is None


def test_stats_ignores_checks_outside_window(db):
    monitor = make_monitor(db)
    db.add(Check(monitor_id=monitor.id, response_ms=100, is_success=True))
    db.commit()
    db.execute(
        text("INSERT INTO checks (monitor_id, checked_at, is_success, response_ms) "
             "VALUES (:m, now() - interval '3 days', false, 50)"),
        {"m": monitor.id},
    )
    db.commit()
    assert fetch_stats(db, "24h")[0]["total_checks"] == 1
    assert fetch_stats(db, "7d")[0]["total_checks"] == 2
