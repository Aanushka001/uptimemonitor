import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Protect write endpoints with a shared API key (constant-time compare)."""
    if not secrets.compare_digest(x_api_key.encode(), settings.api_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
