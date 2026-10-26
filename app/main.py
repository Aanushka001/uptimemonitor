from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Incident, Monitor
from app.routers import incidents, monitors, stats
from app.services.stats import fetch_stats

app = FastAPI(title="Vigil", description="Uptime and incident monitor", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app.include_router(monitors.router)
app.include_router(stats.router)
app.include_router(incidents.router)

if settings.enable_demo_endpoints:
    from app.routers import demo

    app.include_router(demo.router)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def dashboard(request: Request, window: str = "24h", db: Session = Depends(get_db)):
    if window not in ("1h", "24h", "7d", "30d"):
        window = "24h"
    open_incidents = db.execute(
        select(Incident, Monitor.name)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Incident.resolved_at.is_(None))
        .order_by(Incident.started_at.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"stats": fetch_stats(db, window), "open_incidents": open_incidents, "window": window},
    )
