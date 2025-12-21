# app/models_exercise.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from app.models import FK_CHILD_ID


FK_EXERCISE_ID = "exercise.id"


class Exercise(SQLModel, table=True):
    __tablename__ = "exercise"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    # Domain must be non-null(we use it for filtering and reporting)
    domain: str = Field(default="unknown", index=True, nullable=False)

    title: str = Field(default="", nullable=False)
    description: Optional[str] = Field(default=None)

    min_age_months: int = Field(default=0, index=True, nullable=False)
    max_age_months: int = Field(default=240, index=True, nullable=False)

    content_ref: Optional[str] = Field(default=None)

    mastery_target_correct: int = Field(default=8, nullable=False)
    mastery_window: int = Field(default=10, nullable=False)

    is_active: bool = Field(default=True, index=True, nullable=False)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False)


class ChildExerciseProgress(SQLModel, table=True):
    __tablename__ = "child_exercise_progress"  # type: ignore[assignment]
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)

    child_id: int = Field(foreign_key=FK_CHILD_ID, index=True, nullable=False)
    exercise_id: int = Field(foreign_key=FK_EXERCISE_ID,
                             index=True, nullable=False)

    # locked/in_progress/mastered
    status: str = Field(default="in_progress", index=True, nullable=False)

    attempts_total: int = Field(default=0, nullable=False)
    correct_total: int = Field(default=0, nullable=False)

    last_attempt_at: Optional[datetime] = Field(default=None)
    mastered_at: Optional[datetime] = Field(default=None)
