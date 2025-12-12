# api/models_institution.py
from __future__ import annotations

from typing import Optional

from sqlmodel import SQLModel, Field


class Child(SQLModel):
    """
    Lightweight API schema used for linking reports and exercises
    to a specific child and institution.

    This is intentionally NOT mapped as a table (no `table=True`),
    because the real Child ORM model lives in app.models.Child.
    """
    id: str = Field(index=True)
    name: Optional[str] = None

    # Optional: age info if you want it later for age-based exercises
    age_years: Optional[int] = None
    age_months: Optional[int] = None

    # Link to institution (matches institution_id used in routes_institutions.py)
    institution_id: Optional[int] = Field(default=None, index=True)
