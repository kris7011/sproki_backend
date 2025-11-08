# api/models_user.py
from __future__ import annotations
from enum import Enum
from sqlmodel import SQLModel, Field


class Role(str, Enum):
    LEDER = "LEDER"
    PPR = "PPR"
    PERSONALE = "PERSONALE"
    FORAELDER = "FORAELDER"   # brug denne nøgle (uden æ) for enkelhed


class User(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    email: str = Field(index=True)
    role: Role = Field(default=Role.FORAELDER)

# Optional – hvis du har brug for dem senere:


class Institution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
