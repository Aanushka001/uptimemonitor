
import logging
import os
import sys
from pathlib import Path
from psycopg import sql
import psycopg
from psycopg import sql   
logger = logging.getLogger("vigil.migrate")
from typing import LiteralString, cast

from psycopg import sql
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BASELINE_VERSION = "0001_baseline"
LOCK_ID = 727274

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def database_dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def discover() -> list[tuple[str, str]]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [(f.stem, f.read_text(encoding="utf-8")) for f in files]


def applied_versions(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT version FROM schema_migrations"
    ).fetchall()
    return {row[0] for row in rows}


def table_exists(conn: psycopg.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT to_regclass(%s::text)",
        (f"public.{name}",),
    ).fetchone()

    return row is not None and row[0] is not None


def migrate() -> int:
    applied_now = 0

    with psycopg.connect(database_dsn(), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_advisory_lock(%s)",
            (LOCK_ID,),
        )

        try:
            conn.execute(CREATE_TRACKING_TABLE)
            done = applied_versions(conn)

            if not done and table_exists(conn, "monitors"):
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (BASELINE_VERSION,),
                )
                done.add(BASELINE_VERSION)

                logger.info(
                    "existing database detected, recorded %s without running it",
                    BASELINE_VERSION,
                )

            for version, migration_sql in discover():
                if version in done:
                    continue

                with conn.transaction():
                    
                    conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,),
                    )

                logger.info("applied %s", version)
                applied_now += 1

        finally:
            conn.execute(
                "SELECT pg_advisory_unlock(%s)",
                (LOCK_ID,),
            )

    return applied_now


def status() -> None:
    with psycopg.connect(database_dsn(), autocommit=True) as conn:
        conn.execute(CREATE_TRACKING_TABLE)
        done = applied_versions(conn)

    for version, _ in discover():
        state = "applied" if version in done else "pending"
        print(f"{state:8} {version}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if "--status" in sys.argv:
        status()
        return

    count = migrate()
    logger.info("migrations complete, %s applied", count)


if __name__ == "__main__":
    main()
