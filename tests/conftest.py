import os
from pathlib import Path

# Tests must never touch a development database.
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://vigil:vigil@localhost:5432/vigil_test"
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["API_KEY"] = "test-key"
os.environ["ALLOW_PRIVATE_TARGETS"] = "false"
os.environ["ENABLE_DEMO_ENDPOINTS"] = "false"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

SCHEMA = (Path(__file__).parent.parent / "sql" / "schema.sql").read_text()


@pytest.fixture()
def db():
    """A clean PostgreSQL schema for each test. Skips if no database is reachable."""
    from app.db import SessionLocal, engine

    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alerts, incidents, checks, monitors CASCADE"))
            conn.exec_driver_sql(SCHEMA)
    except OperationalError:
        if os.environ.get("REQUIRE_DB"):
            raise  # CI must fail loudly, never skip silently
        pytest.skip("PostgreSQL is not reachable; set TEST_DATABASE_URL to run integration tests")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


AUTH = {"X-API-Key": "test-key"}
