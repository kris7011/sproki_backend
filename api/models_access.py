# api/models_access.py
# pyright: reportGeneralTypeIssues=none, reportAttributeAccessIssue=none, reportCallIssue=none

from __future__ import annotations

import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class ChildAccess(SQLModel, table=True):
    __tablename__ = "api_child_access"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    child_id: int = Field(index=True, foreign_key="child.id")
    user_id: str = Field(index=True, foreign_key="api_user.id")

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
