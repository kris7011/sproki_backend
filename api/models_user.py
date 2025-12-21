# pyright: reportGeneralTypeIssues=none, reportAttributeAccessIssue=none, reportCallIssue=none

from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


class Role(str, Enum):
    LEDER = "LEDER"
    PPR = "PPR"
    PERSONALE = "PERSONALE"
    FORAELDER = "FORAELDER"


class User(SQLModel, table=True):
    __tablename__ = "api_user"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True, index=True)
    email: str = Field(index=True)
    role: Role = Field(default=Role.FORAELDER)

    institution_id: Optional[int] = Field(
        default=None, foreign_key="institution.id")
    # VIGTIGT: fjern relationship her, den trigger Optional['Institution']-fejlen


class Invite(SQLModel, table=True):
    __tablename__ = "api_invite"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    token: str = Field(index=True)
    email: str
    role: Role

    institution_id: int = Field(foreign_key="institution.id")
    created_by_user_id: str = Field(foreign_key="api_user.id")
    # Også her: ingen relationship
