from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Exercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str
    title: str
    age_min: int
    age_max: int
    media_url: Optional[str] = None
    is_active: bool = True


class ExerciseAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: str
    exercise_id: int
    correct: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)
