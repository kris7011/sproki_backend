from __future__ import annotations

# Backwards-compatible re-exports of domain / exercise models.
# All actual SQLModel table definitions live in app.models.

from .models import (  # type: ignore F401
    Domain,
    DomainThreshold,
    ExerciseCategory,
    ExerciseItem,
    ExerciseAssignment,
    ExerciseAttempt,
    ExerciseProgress,
)
