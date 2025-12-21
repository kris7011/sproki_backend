from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from api.models_user import User, Invite


class Institution(SQLModel, table=True):
    __tablename__ = "institution"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    users: List["User"] = Relationship(back_populates="institution")
    invites: List["Invite"] = Relationship(back_populates="institution")
