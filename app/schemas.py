from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=2048)
    interval_seconds: int = Field(default=60, ge=10, le=3600)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    failure_threshold: int = Field(default=3, ge=1, le=10)


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=8, max_length=2048)
    interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    timeout_seconds: int | None = Field(default=None, ge=1, le=30)
    failure_threshold: int | None = Field(default=None, ge=1, le=10)
    is_active: bool | None = None


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_seconds: int
    timeout_seconds: int
    failure_threshold: int
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checked_at: datetime
    status_code: int | None
    response_ms: int | None
    is_success: bool
    error: str | None


class IncidentOut(BaseModel):
    id: int
    monitor_id: int
    monitor_name: str
    started_at: datetime
    resolved_at: datetime | None
    last_error: str | None
