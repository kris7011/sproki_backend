# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

# ------------------------ Common FK constants ------------------------

FK_CHILD_ID = "child.id"
FK_PARENT_ID = "parent.id"
FK_STAFF_ID = "staff.id"
FK_INSTITUTION_ID = "institution.id"
FK_DOMAIN_ID = "domain.id"
FK_EXERCISECATEGORY_ID = "exercisecategory.id"
FK_EXERCISEITEM_ID = "exerciseitem.id"

# ------------------------ Many-to-many links ------------------------


class ChildParentLink(SQLModel, table=True):
    child_id: int = Field(foreign_key=FK_CHILD_ID, primary_key=True)
    parent_id: int = Field(foreign_key=FK_PARENT_ID, primary_key=True)


class ChildStaffLink(SQLModel, table=True):
    child_id: int = Field(foreign_key=FK_CHILD_ID, primary_key=True)
    staff_id: int = Field(foreign_key=FK_STAFF_ID, primary_key=True)


# ------------------------ Institution & relations ------------------------


class Institution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key=FK_INSTITUTION_ID)
    name: str
    email: str
    role: str = Field(default="staff")


class Parent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age_years: int
    age_months: int
    institution_id: int = Field(foreign_key=FK_INSTITUTION_ID)
    ppr_consent: bool = Field(default=False)
    report_path: Optional[str] = None
    report_filename: Optional[str] = None


# ------------------------ Domains & Thresholds ------------------------


class Domain(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    name: str
    title: Optional[str] = None


class DomainThreshold(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain_id: int = Field(foreign_key=FK_DOMAIN_ID)

    age_years_min: int
    age_months_min: int
    age_years_max: int
    age_months_max: int

    score_min_green: int
    score_min_yellow: int


# ------------------------ Exercises ------------------------


class ExerciseCategory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain_id: int = Field(foreign_key=FK_DOMAIN_ID)
    code: str
    title: str
    description: Optional[str] = None
    age_years_min: int = Field(default=0)
    age_months_min: int = Field(default=0)
    age_years_max: int = Field(default=10)
    age_months_max: int = Field(default=11)
    target_success_rate: float = Field(default=0.8)


class ExerciseItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    prompt: str
    media_url: Optional[str] = None
    difficulty: int = Field(default=1)


# ------------------------ Assignments & Progress ------------------------


class ExerciseAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_completed: bool = Field(default=False)


class ExerciseAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    item_id: int = Field(foreign_key=FK_EXERCISEITEM_ID)
    is_correct: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExerciseProgress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    attempts_total: int = Field(default=0)
    correct_total: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
