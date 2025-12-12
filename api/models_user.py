# pyright: reportGeneralTypeIssues=none, reportAttributeAccessIssue=none, reportCallIssue=none

from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models_institution import Institution


class Role(str, Enum):
    LEDER = "LEDER"
    PPR = "PPR"
    PERSONALE = "PERSONALE"
    FORAELDER = "FORAELDER"  # no æ/ø/å in key, db-friendly


class User(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    email: str = Field(index=True)
    role: Role = Field(default=Role.FORAELDER)

    institution_id: Optional[int] = Field(
        default=None, foreign_key="institution.id"
    )
    institution: Optional["Institution"] = Relationship(back_populates="users")


class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    token: str = Field(index=True)
    email: str
    role: Role

    institution_id: int = Field(foreign_key="institution.id")
    created_by_user_id: str = Field(foreign_key="user.id")

    institution: Optional["Institution"] = Relationship(
        back_populates="invites")
