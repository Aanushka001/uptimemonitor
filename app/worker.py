"""Polling worker. Run with: python -m app.worker"""
import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.models import Monitor
from app.services.checker import CheckResult, run_check
from app.services.incidents import record_result

logger = logging.getLogger("vigil.worker")
stop_event = threading.Event()

DUE_CONDITION = text(
    "(last_checked_at IS NULL "
    "OR last_checked_at + (interval_seconds * interval '1 second') <= now())"
)


def find_due_monitors(db) -> list[Monitor]:
    return list(
        db.execute(select(Monitor).where(Monitor.is_active.is_(True), DUE_CONDITION)).scalars()
    )


def _check(monitor: Monitor) -> CheckResult:
    return run_check(monitor.url, monitor.timeout_seconds, settings.allow_private_targets)


def tick(pool: ThreadPoolExecutor) -> int:
    """Check every due monitor once. Returns how many were checked."""
    with SessionLocal() as db:
        due = find_due_monitors(db)
        if not due:
            return 0
        # Network calls run in threads; they never touch the database session.
        results = list(pool.map(_check, due))
        for monitor, result in zip(due, results):
            action = record_result(db, monitor, result)
            logger.info(
                "checked monitor=%s ok=%s status=%s ms=%s action=%s",
                monitor.id, result.is_success, result.status_code, result.response_ms, action,
            )
        return len(due)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs full request URLs at INFO; those can contain secrets
    # (the Telegram bot token, or tokens in monitored URLs). Keep them out of logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    logger.info("worker started (tick=%ss, threads=%s)", settings.worker_tick_seconds, settings.worker_threads)

    with ThreadPoolExecutor(max_workers=settings.worker_threads) as pool:
        while not stop_event.is_set():
            try:
                tick(pool)
            except Exception:
                logger.exception("tick failed; continuing")
            stop_event.wait(settings.worker_tick_seconds)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
