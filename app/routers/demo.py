"""Switchable endpoint for repeatable incident demos. Enabled only when
ENABLE_DEMO_ENDPOINTS=true. Not meant for production."""
from fastapi import APIRouter, Depends, HTTPException

from app.security import require_api_key

router = APIRouter(prefix="/demo", tags=["demo"])
_state = {"healthy": True}


@router.get("/flaky")
def flaky():
    if not _state["healthy"]:
        raise HTTPException(503, "demo endpoint is switched off")
    return {"status": "ok"}


@router.post("/flaky/{mode}", dependencies=[Depends(require_api_key)])
def set_flaky(mode: str):
    if mode not in ("up", "down"):
        raise HTTPException(422, "mode must be 'up' or 'down'")
    _state["healthy"] = mode == "up"
    return {"healthy": _state["healthy"]}
