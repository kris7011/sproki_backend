from __future__ import annotations

# Backwards-compatible re-exports of learning / threshold / exercise models.
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

# Backwards compatible alias for legacy imports:
# Older code does: `from app.models_learning import Exercise`
# We now use ExerciseItem as the concrete table, so map Exercise -> ExerciseItem.
Exercise = ExerciseItem
