import logging
import os
import signal
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import bindparam, select, text

from app.config import settings
from app.db import SessionLocal
from app.models import Monitor
from app.services.checker import CheckResult, run_check
from app.services.incidents import record_result

logger = logging.getLogger("vigil.worker")
stop_event = threading.Event()

WORKER_ID = socket.gethostname()
CLAIM_SECONDS = int(os.environ.get("WORKER_CLAIM_SECONDS", "120"))

DUE_CONDITION = text(
    "(last_checked_at IS NULL "
    "OR last_checked_at + (interval_seconds * interval '1 second') <= now())"
)

CLAIM_SQL = text(
    """
    UPDATE monitors
    SET claimed_until = now() + CAST(:lease AS integer) * interval '1 second'
    WHERE id IN (
        SELECT id FROM monitors
        WHERE is_active
          AND (last_checked_at IS NULL
               OR last_checked_at + (interval_seconds * interval '1 second') <= now())
          AND (claimed_until IS NULL OR claimed_until < now())
        ORDER BY last_checked_at NULLS FIRST, id
        LIMIT :batch
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id
    """
)

RELEASE_SQL = text("UPDATE monitors SET claimed_until = NULL WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


def find_due_monitors(db) -> list[Monitor]:
    return list(
        db.execute(select(Monitor).where(Monitor.is_active.is_(True), DUE_CONDITION)).scalars()
    )


def claim_due_monitors(db, limit: int) -> list[int]:
    rows = db.execute(CLAIM_SQL, {"lease": CLAIM_SECONDS, "batch": limit}).all()
    db.commit()
    return [row[0] for row in rows]


def release_claims(db, ids: list[int]) -> None:
    if not ids:
        return
    db.execute(RELEASE_SQL, {"ids": ids})
    db.commit()


def _check(job: tuple[str, int]) -> CheckResult:
    url, timeout_seconds = job
    return run_check(url, timeout_seconds, settings.allow_private_targets)


def tick(pool: ThreadPoolExecutor) -> int:
    with SessionLocal() as db:
        ids = claim_due_monitors(db, settings.worker_threads)
        if not ids:
            return 0
        try:
            monitors = list(db.execute(select(Monitor).where(Monitor.id.in_(ids))).scalars())
            monitor_ids = [m.id for m in monitors]
            jobs = [(m.url, m.timeout_seconds) for m in monitors]
            results = list(pool.map(_check, jobs))
            for monitor_id, monitor, result in zip(monitor_ids, monitors, results):
                try:
                    action = record_result(db, monitor, result)
                except Exception:
                    db.rollback()
                    logger.exception("recording failed monitor=%s", monitor_id)
                    continue
                logger.info(
                    "worker=%s checked monitor=%s ok=%s status=%s ms=%s action=%s",
                    WORKER_ID, monitor_id, result.is_success, result.status_code,
                    result.response_ms, action,
                )
        finally:
            db.rollback()
            release_claims(db, ids)
        return len(ids)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    logger.info(
        "worker=%s started (tick=%ss, threads=%s, claim=%ss)",
        WORKER_ID, settings.worker_tick_seconds, settings.worker_threads, CLAIM_SECONDS,
    )

    with ThreadPoolExecutor(max_workers=settings.worker_threads) as pool:
        while not stop_event.is_set():
            try:
                tick(pool)
            except Exception:
                logger.exception("tick failed; continuing")
            stop_event.wait(settings.worker_tick_seconds)
    logger.info("worker=%s stopped", WORKER_ID)


if __name__ == "__main__":
    main()