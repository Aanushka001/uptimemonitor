from sqlalchemy import text
from sqlalchemy.orm import Session

WINDOWS = {"1h": "1 hour", "24h": "24 hours", "7d": "7 days", "30d": "30 days"}

STATS_SQL = text(
    """
    SELECT m.id,
           m.name,
           m.url,
           m.is_active,
           m.last_checked_at,
           COUNT(c.id)                                              AS total_checks,
           ROUND(100.0 * COUNT(c.id) FILTER (WHERE c.is_success)
                 / NULLIF(COUNT(c.id), 0), 2)                       AS uptime_pct,
           ROUND(AVG(c.response_ms))                                AS avg_ms,
           ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY c.response_ms)::numeric) AS p95_ms,
           EXISTS (SELECT 1 FROM incidents i
                   WHERE i.monitor_id = m.id AND i.resolved_at IS NULL) AS has_open_incident
    FROM monitors m
    LEFT JOIN checks c
           ON c.monitor_id = m.id
          AND c.checked_at >= now() - CAST(:window AS interval)
    WHERE (CAST(:monitor_id AS integer) IS NULL OR m.id = CAST(:monitor_id AS integer))
    GROUP BY m.id
    ORDER BY m.name
    """
)


def fetch_stats(db: Session, window: str = "24h", monitor_id: int | None = None) -> list[dict]:
    if window not in WINDOWS:
        raise ValueError(f"window must be one of {sorted(WINDOWS)}")
    rows = db.execute(STATS_SQL, {"window": WINDOWS[window], "monitor_id": monitor_id}).mappings().all()
    stats = []
    for row in rows:
        item = dict(row)
        for key in ("uptime_pct", "avg_ms", "p95_ms"):
            if item[key] is not None:
                item[key] = float(item[key])
        if not item["is_active"]:
            item["status"] = "paused"
        elif item["has_open_incident"]:
            item["status"] = "down"
        elif item["total_checks"] == 0:
            item["status"] = "pending"
        else:
            item["status"] = "up"
        stats.append(item)
    return stats
