# === FILE: app/models_institution.py
from __future__ import annotations
from app.routers import institutions, children
from app.db import init_db
from fastapi import FastAPI
import os
from sqlmodel import SQLModel, Session, create_engine
from app.services.mailer import mailer, MailMessage
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.models_institution import (
    Institution, InstitutionCreate, Staff, StaffCreate
)
from app.auth import require_role, User
from sqlmodel import Session, select
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Institution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    address: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    staff: List["Staff"] = Relationship(back_populates="institution")
    children: List["Child"] = Relationship(back_populates="institution")


class Staff(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    role: str = "staff"  # staff by default

    institution_id: int = Field(foreign_key="institution.id")
    institution: Institution | None = Relationship(back_populates="staff")


class Parent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age_years: int
    age_months: int

    institution_id: int = Field(foreign_key="institution.id")
    institution: Institution | None = Relationship(back_populates="children")

    ppr_consent: bool = False


class ChildParentLink(SQLModel, table=True):
    child_id: int = Field(foreign_key="child.id", primary_key=True)
    parent_id: int = Field(foreign_key="parent.id", primary_key=True)


class ChildStaffLink(SQLModel, table=True):
    child_id: int = Field(foreign_key="child.id", primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", primary_key=True)


# DTOs
class InstitutionCreate(SQLModel):
    name: str
    address: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class StaffCreate(SQLModel):
    name: str
    email: str


class ParentCreate(SQLModel):
    name: str
    email: str


class ChildCreate(SQLModel):
    name: str
    age_years: int
    age_months: int
    institution_id: int
    ppr_consent: bool = False
    parent_emails: list[str] = []
    staff_ids: list[int] = []


# === FILE: app/auth.py

# Minimal stub. Integrate with your existing auth.

class User:
    def __init__(self, user_id: int, role: str):
        self.id = user_id
        self.role = role


def get_current_user() -> User:
    # TODO: replace with real auth (JWT/MitID integration)
    return User(user_id=1, role="leader")


def require_role(roles: list[str]):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _inner


# === FILE: app/services/mailer.py


@dataclass
class MailMessage:
    to: str
    subject: str
    html: str


class Mailer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or "console"

    def send(self, msg: MailMessage):
        # Replace with SendGrid/Mailgun/SMTP; for now print to console for visibility
        print(
            f"[MAIL->{self.provider}] to={msg.to} subject={msg.subject}\n{msg.html}")


mailer = Mailer()


# === FILE: app/routers/institutions.py


router = APIRouter(prefix="/institutions", tags=["institutions"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.post("/", response_model=Institution)
def create_institution(dto: InstitutionCreate, user: User = Depends(require_role(["leader"])), session: Session = Depends(get_session)):
    inst = Institution(**dto.dict())
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.get("/mine", response_model=list[Institution])
def list_my_institutions(user: User = Depends(require_role(["leader"])), session: Session = Depends(get_session)):
    # If institutions are owned by user: add owner_id column. For now, return all for leader.
    result = session.exec(select(Institution)).all()
    return result


@router.post("/{institution_id}/staff", response_model=Staff)
def add_staff(institution_id: int, dto: StaffCreate, user: User = Depends(require_role(["leader"])), session: Session = Depends(get_session)):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    staff = Staff(**dto.dict(), institution_id=institution_id)
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


@router.get("/{institution_id}/staff", response_model=list[Staff])
def list_staff(institution_id: int, user: User = Depends(require_role(["leader", "staff"])), session: Session = Depends(get_session)):
    q = select(Staff).where(Staff.institution_id == institution_id)
    return session.exec(q).all()


# === FILE: app/routers/children.py


router = APIRouter(prefix="/children", tags=["children"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.post("/", response_model=Child)
async def create_child(
    name: str = Form(...),
    age_years: int = Form(...),
    age_months: int = Form(...),
    institution_id: int = Form(...),
    ppr_consent: bool = Form(False),
    parent_emails: List[str] = Form([]),
    staff_ids: List[int] = Form([]),
    report_file: UploadFile = File(None),
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    child = Child(
        name=name,
        age_years=age_years,
        age_months=age_months,
        institution_id=institution_id,
        ppr_consent=ppr_consent,
    )
    session.add(child)
    session.commit()
    session.refresh(child)

    for email in parent_emails:
        # Upsert Parent
        parent = session.exec(select(Parent).where(
            Parent.email == email)).first()
        if not parent:
            parent = Parent(name=email.split("@")[0], email=email)
            session.add(parent)
            session.commit()
            session.refresh(parent)
        link = ChildParentLink(child_id=child.id, parent_id=parent.id)
        session.add(link)

    for sid in staff_ids:
        if session.get(Staff, sid):
            session.add(ChildStaffLink(child_id=child.id, staff_id=sid))

    session.commit()

    if report_file is not None:
        # TODO: store file to S3/disk and reference it
        content = await report_file.read()
        print(
            f"[REPORT-UPLOAD] child={child.id} bytes={len(content)} name={report_file.filename}")

    # Notify parents via mail
    for email in parent_emails:
        mailer.send(MailMessage(
            to=email,
            subject="Dit barn er oprettet i Sproki",
            html=f"<p>Hej! Dit barn '{child.name}' er oprettet. Log ind med MitID via appen for at komme i gang.</p>"
        ))

    # Optional: notify PPR
    if ppr_consent:
        # Replace with configured PPR email
        mailer.send(MailMessage(
            to="ppr@example.com",
            subject=f"PPR-tilknytning: {child.name}",
            html=f"<p>Barnet '{child.name}' er markeret til PPR. Institution ID: {institution_id}</p>"
        ))

    return child


@router.get("/by-institution/{institution_id}", response_model=list[Child])
async def list_children_for_institution(
    institution_id: int,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_session),
):
    q = select(Child).where(Child.institution_id == institution_id)
    return session.exec(q).all()


# === FILE: app/db.py

DATABASE_URL = os.getenv("SPROKI_DB_URL", "sqlite:///./sproki.db")
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    # For initial bootstrap; switch to Alembic for prod.
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


# === FILE: app/main_patch.py

app = FastAPI(title="Sproki API – Sprint 1")
init_db()

app.include_router(institutions.router)
app.include_router(children.router)

# Run: uvicorn app.main_patch:app --reload
