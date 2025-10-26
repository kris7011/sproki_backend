# app/models.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Literal
from sqlmodel import SQLModel, Field, Relationship

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

    children: List["Child"] = Relationship(back_populates="institution")
    staff: List["Staff"] = Relationship(back_populates="institution")


class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key=FK_INSTITUTION_ID)
    name: str
    email: str
    role: str = "staff"

    institution: Optional[Institution] = Relationship(back_populates="staff")
    children: List["Child"] = Relationship(
        back_populates="staff_members", link_model=ChildStaffLink
    )


class Parent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    children: List["Child"] = Relationship(
        back_populates="parents", link_model=ChildParentLink
    )


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age_years: int
    age_months: int
    institution_id: int = Field(foreign_key=FK_INSTITUTION_ID)
    ppr_consent: bool = False
    report_path: Optional[str] = None
    report_filename: Optional[str] = None

    institution: Optional[Institution] = Relationship(
        back_populates="children")
    parents: List[Parent] = Relationship(
        back_populates="children", link_model=ChildParentLink
    )
    staff_members: List[Staff] = Relationship(
        back_populates="children", link_model=ChildStaffLink
    )


# ------------------------ Domains & Thresholds ------------------------
class Domain(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    title: str

    thresholds: List["DomainThreshold"] = Relationship(back_populates="domain")


class DomainThreshold(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain_id: int = Field(foreign_key=FK_DOMAIN_ID)
    age_years_min: int
    age_months_min: int
    age_years_max: int
    age_months_max: int
    score_min_green: int
    score_min_yellow: int

    domain: Optional[Domain] = Relationship(back_populates="thresholds")


# ------------------------ Exercises ------------------------
class ExerciseCategory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    domain_id: int = Field(foreign_key=FK_DOMAIN_ID)
    code: str
    title: str
    description: Optional[str] = None
    age_years_min: int = 0
    age_months_min: int = 0
    age_years_max: int = 10
    age_months_max: int = 11
    target_success_rate: float = 0.8

    domain: Optional[Domain] = Relationship()
    items: List["ExerciseItem"] = Relationship(back_populates="category")


class ExerciseItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    prompt: str
    media_url: Optional[str] = None
    difficulty: int = 1

    category: Optional[ExerciseCategory] = Relationship(back_populates="items")


# ------------------------ Assignments & Progress ------------------------
class ExerciseAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_completed: bool = False

    child: Optional[Child] = Relationship()
    category: Optional[ExerciseCategory] = Relationship()


class ExerciseAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    item_id: int = Field(foreign_key=FK_EXERCISEITEM_ID)
    is_correct: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)

    child: Optional[Child] = Relationship()
    item: Optional[ExerciseItem] = Relationship()


class ExerciseProgress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key=FK_CHILD_ID)
    category_id: int = Field(foreign_key=FK_EXERCISECATEGORY_ID)
    attempts_total: int = 0
    correct_total: int = 0
    success_rate: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    child: Optional[Child] = Relationship()
    category: Optional[ExerciseCategory] = Relationship()
