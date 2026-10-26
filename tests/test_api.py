from sqlalchemy import select

from app.models import Check, Incident
from tests.conftest import AUTH

PUBLIC_URL = "https://8.8.8.8/health"


def create(client, **overrides):
    body = {"name": "Public API", "url": PUBLIC_URL, **overrides}
    return client.post("/monitors", json=body, headers=AUTH)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_write_endpoints_require_api_key(client):
    assert client.post("/monitors", json={"name": "x", "url": PUBLIC_URL}).status_code == 401
    assert client.post("/monitors", json={"name": "x", "url": PUBLIC_URL},
                       headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_list_get_update_delete(client):
    created = create(client)
    assert created.status_code == 201
    monitor_id = created.json()["id"]
    assert created.json()["failure_threshold"] == 3

    assert len(client.get("/monitors").json()) == 1
    assert client.get(f"/monitors/{monitor_id}").json()["name"] == "Public API"

    patched = client.patch(f"/monitors/{monitor_id}", json={"is_active": False}, headers=AUTH)
    assert patched.status_code == 200 and patched.json()["is_active"] is False

    assert client.delete(f"/monitors/{monitor_id}", headers=AUTH).status_code == 204
    assert client.get(f"/monitors/{monitor_id}").status_code == 404


def test_private_and_non_http_urls_are_rejected(client):
    assert create(client, url="http://127.0.0.1:8000/").status_code == 422
    assert create(client, url="http://169.254.169.254/latest/").status_code == 422
    assert create(client, url="ftp://example.com/file").status_code == 422


def test_field_limits_are_validated(client):
    assert create(client, interval_seconds=1).status_code == 422
    assert create(client, failure_threshold=0).status_code == 422


def test_checks_and_incidents_endpoints(client, db):
    monitor_id = create(client).json()["id"]
    db.add(Check(monitor_id=monitor_id, status_code=500, response_ms=90, is_success=False, error="HTTP 500"))
    db.add(Incident(monitor_id=monitor_id, last_error="HTTP 500"))
    db.commit()

    checks = client.get(f"/monitors/{monitor_id}/checks?limit=10").json()
    assert len(checks) == 1 and checks[0]["error"] == "HTTP 500"

    open_incidents = client.get("/incidents?status=open").json()
    assert len(open_incidents) == 1 and open_incidents[0]["monitor_name"] == "Public API"
    assert client.get("/incidents?status=resolved").json() == []


def test_stats_endpoint_and_window_validation(client, db):
    monitor_id = create(client).json()["id"]
    db.add(Check(monitor_id=monitor_id, response_ms=100, is_success=True))
    db.commit()

    stats = client.get(f"/monitors/{monitor_id}/stats?window=24h").json()
    assert stats["uptime_pct"] == 100.0 and stats["status"] == "up"
    assert client.get(f"/monitors/{monitor_id}/stats?window=banana").status_code == 422
    assert client.get("/monitors/9999/stats").status_code == 404


def test_dashboard_renders(client):
    create(client, name="Shown <b>on</b> dashboard")
    page = client.get("/")
    assert page.status_code == 200
    assert "Vigil" in page.text
    assert "<b>on</b>" not in page.text  # user input is escaped
