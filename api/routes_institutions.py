# api/routes_institutions.py
# pyright: reportUndefinedVariable=none, reportInvalidTypeArguments=none, reportInvalidTypeForm=none, reportMissingImports=none, reportPrivateImportUsage=none

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic.fields import Field as PField
from sqlmodel import Session, select

from api.db import engine
from .auth import require_roles
from .models_user import Institution, User, Role, Invite
from .email_stub import send_email

router = APIRouter(prefix="/institutions", tags=["institutions"])

ERR_NOT_YOUR_INST = "Not your institution"

# ---------- Schemas ----------


class InstitutionCreate(BaseModel):
    name: str = PField(min_length=2, max_length=200)


class InstitutionOut(BaseModel):
    id: int
    name: str


class StaffOut(BaseModel):
    id: str
    email: str
    role: Role


class ChildCreate(BaseModel):
    childId: str
    name: str | None = None
    parentEmails: list[str] = PField(default_factory=list)


class InviteCreate(BaseModel):
    email: str
    role: Role

# ---------- Routes ----------


@router.post("", response_model=InstitutionOut)
def create_institution(
    payload: InstitutionCreate,
    user: User = Depends(require_roles(Role.LEDER)),
):
    with Session(engine) as s:
        inst = Institution(name=payload.name)
        s.add(inst)
        s.commit()
        s.refresh(inst)

        u = s.exec(select(User).where(User.id == user.id)).one_or_none()
        if u and not u.institutionId:
            u.institutionId = inst.id
            s.add(u)
            s.commit()

        return InstitutionOut(id=int(inst.id), name=inst.name)


@router.get("/{institution_id}/staff", response_model=list[StaffOut])
def list_staff(
    institution_id: int,
    user: User = Depends(require_roles(Role.LEDER, Role.PERSONALE, Role.PPR)),
):
    with Session(engine) as s:
        if user.role != Role.PPR and user.institutionId != institution_id:
            raise HTTPException(status_code=403, detail=ERR_NOT_YOUR_INST)

        rows = s.exec(select(User).where(
            User.institutionId == institution_id)).all()
        return [StaffOut(id=u.id, email=u.email, role=u.role) for u in rows]


@router.post("/{institution_id}/staff/invite")
def invite_staff(
    institution_id: int,
    payload: InviteCreate,
    user: User = Depends(require_roles(Role.LEDER)),
):
    if payload.role not in {Role.PERSONALE, Role.LEDER, Role.PPR}:
        raise HTTPException(
            status_code=400,
            detail="Role must be LEDER/PERSONALE/PPR for staff invites",
        )

    with Session(engine) as s:
        if user.institutionId != institution_id:
            raise HTTPException(status_code=403, detail=ERR_NOT_YOUR_INST)

        token = secrets.token_urlsafe(32)
        inv = Invite(
            token=token,
            email=payload.email.lower(),
            role=payload.role,
            institutionId=institution_id,
            createdByUserId=user.id,
        )
        s.add(inv)
        s.commit()

        accept_url = f"/accept-invite?token={token}"
        send_email(
            to=payload.email,
            subject="[Sproki] Invitation",
            text=f"Du er inviteret til Sproki som {payload.role}. Klik: {accept_url}",
        )
        return {"ok": True}


@router.post("/{institution_id}/children")
def create_child_for_institution(
    institution_id: int,
    payload: ChildCreate,
    user: User = Depends(require_roles(Role.LEDER, Role.PERSONALE)),
):
    # Local import to avoid circular import at import time
    from .models_institution import Child

    with Session(engine) as s:
        if user.institutionId != institution_id:
            raise HTTPException(status_code=403, detail=ERR_NOT_YOUR_INST)

        c = s.exec(select(Child).where(
            Child.id == payload.childId)).one_or_none()
        if not c:
            c = Child(id=payload.childId, name=payload.name)
            s.add(c)
            s.commit()
            s.refresh(c)

        return {"ok": True, "childId": c.id}
