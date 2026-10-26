-- Vigil database schema (PostgreSQL 14+)

CREATE TABLE IF NOT EXISTS monitors (
    id                 SERIAL PRIMARY KEY,
    name               VARCHAR(100)  NOT NULL,
    url                VARCHAR(2048) NOT NULL,
    interval_seconds   INTEGER       NOT NULL DEFAULT 60
                       CHECK (interval_seconds BETWEEN 10 AND 3600),
    timeout_seconds    INTEGER       NOT NULL DEFAULT 10
                       CHECK (timeout_seconds BETWEEN 1 AND 30),
    failure_threshold  INTEGER       NOT NULL DEFAULT 3
                       CHECK (failure_threshold BETWEEN 1 AND 10),
    is_active          BOOLEAN       NOT NULL DEFAULT TRUE,
    last_checked_at    TIMESTAMPTZ,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checks (
    id           BIGSERIAL PRIMARY KEY,
    monitor_id   INTEGER     NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_code  INTEGER,
    response_ms  INTEGER,
    is_success   BOOLEAN     NOT NULL,
    error        VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS incidents (
    id           SERIAL PRIMARY KEY,
    monitor_id   INTEGER     NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ,
    last_error   VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS alerts (
    id           SERIAL PRIMARY KEY,
    incident_id  INTEGER     NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    kind         VARCHAR(20) NOT NULL CHECK (kind IN ('down', 'recovered')),
    sent_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered    BOOLEAN     NOT NULL
);

-- Serves "latest N checks" and "checks in a time window" for one monitor.
CREATE INDEX IF NOT EXISTS idx_checks_monitor_time
    ON checks (monitor_id, checked_at DESC);

-- At most one open incident per monitor, enforced by the database itself.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_incident_per_monitor
    ON incidents (monitor_id) WHERE resolved_at IS NULL;
