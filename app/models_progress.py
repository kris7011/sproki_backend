from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class DomainProgress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key="child.id")
    domain: str
    score: int
    color: str  # "red" | "yellow" | "green"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
