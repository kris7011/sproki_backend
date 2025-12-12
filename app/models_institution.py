# app/models_institution.py
from __future__ import annotations

"""
Backwards-compatible re-exports of institution- and child-related models.

Historically, some code imported these models from app.models_institution.
All actual SQLModel table definitions now live in app.models, so this module
just re-exports them to avoid breaking older imports.
"""

from .models import (  # noqa: F401
    Child,
    Parent,
    Staff,
    Institution,
    ChildParentLink,
    ChildStaffLink,
)

__all__ = [
    "Child",
    "Parent",
    "Staff",
    "Institution",
    "ChildParentLink",
    "ChildStaffLink",
]
