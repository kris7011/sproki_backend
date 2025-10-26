from __future__ import annotations
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class ChildParentLink(SQLModel, table=True):
    child_id: int = Field(foreign_key="child.id", primary_key=True)
    parent_id: int = Field(foreign_key="parent.id", primary_key=True)


class ChildStaffLink(SQLModel, table=True):
    child_id: int = Field(foreign_key="child.id", primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", primary_key=True)


class Institution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    # 1-til-mange til Child og Staff
    children: list["Child"] = Relationship(back_populates="institution")
    staff: list["Staff"] = Relationship(back_populates="institution")


class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="institution.id")
    name: str
    email: str
    role: str = Field(default="staff")

    # mange-til-1 til Institution
    institution: Optional["Institution"] = Relationship(back_populates="staff")

    # mange-til-mange til Child via linktabel
    children: list["Child"] = Relationship(
        back_populates="staff_members",
        link_model=ChildStaffLink,
    )


class Parent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    # mange-til-mange til Child via linktabel
    children: list["Child"] = Relationship(
        back_populates="parents",
        link_model=ChildParentLink,
    )


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age_years: int
    age_months: int
    institution_id: int = Field(foreign_key="institution.id")
    ppr_consent: bool = Field(default=False)
    report_path: Optional[str] = None
    report_filename: Optional[str] = None

    # mange-til-1 til Institution
    institution: Optional["Institution"] = Relationship(
        back_populates="children")

    # mange-til-mange til Parent og Staff via linktabeller
    parents: list["Parent"] = Relationship(
        back_populates="children",
        link_model=ChildParentLink,
    )
    staff_members: list["Staff"] = Relationship(
        back_populates="children",
        link_model=ChildStaffLink,
    )
