# api/models_report.py
from __future__ import annotations
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    child_id: str = Field(index=True)
    category: str = Field(index=True)
    score: float
    color_zone: str = Field(index=True)
    points_to_green: float = Field(default=0.0)
    age_years: int
    age_months: int
    created_at: datetime = Field(default_factory=_utcnow, index=True)
