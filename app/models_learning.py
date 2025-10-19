from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class DomainThreshold(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    age_years: int
    age_months: int
    yellow_min: int
    green_min: int


class Exercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    payload_json: str  # JSON blob for content


class ExerciseAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int
    exercise_id: int
    correct: bool
    ts_utc: datetime = Field(default_factory=datetime.utcnow)
