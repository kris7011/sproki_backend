from __future__ import annotations

from typing import Optional
from sqlmodel import SQLModel, Field


class Institution(SQLModel, table=True):
    __tablename__ = "institution"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    # Fjern users/invites Relationship her – det kan vi tilføje senere, når alt kører stabilt
