# === FILE: app/routers/institutions.py
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import require_role, User
from app.models_institution import Institution, Staff
from app.db import get_session as get_db_session

router = APIRouter(prefix="/institutions", tags=["institutions"])

INSTITUTION_NOT_FOUND = "Institution not found"


# ---- DTOs (lokale – ingen EmailStr for at undgå email-validator) ----
class InstitutionCreate(BaseModel):
    name: str
    address: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class StaffCreate(BaseModel):
    name: str
    email: str  # brug str (ikke EmailStr) for at undgå ekstra dependency
    role: str = "staff"


class InstitutionPatch(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


def _ensure_owner_if_exists(inst: Institution, user: User) -> None:
    if hasattr(Institution, "owner_id"):
        owner_id = getattr(inst, "owner_id", None)
        if owner_id is not None and user.role == "leader" and owner_id != user.id:
            raise HTTPException(
                status_code=403, detail="Not allowed for this institution")


@router.post("/", response_model=Institution)
def create_institution(
    dto: InstitutionCreate,
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    inst = Institution(
        **{k: v for k, v in dto.model_dump().items() if hasattr(Institution, k)})

    if hasattr(Institution, "owner_id"):
        setattr(inst, "owner_id", user.id)

    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.get("/mine", response_model=list[Institution])
def list_my_institutions(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    if hasattr(Institution, "owner_id"):
        q = select(Institution).where(
            getattr(Institution, "owner_id") == user.id)
    else:
        q = select(Institution)
    return session.exec(q).all()


@router.get("/{institution_id}", response_model=Institution)
def get_institution(
    institution_id: int,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_db_session),
):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)
    _ensure_owner_if_exists(inst, user)
    return inst


@router.patch("/{institution_id}", response_model=Institution)
def update_institution(
    institution_id: int,
    patch: InstitutionPatch,
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)

    _ensure_owner_if_exists(inst, user)

    for k, v in patch.model_dump(exclude_unset=True).items():
        if hasattr(inst, k):
            setattr(inst, k, v)

    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.post("/{institution_id}/staff", response_model=Staff)
def add_staff(
    institution_id: int,
    dto: StaffCreate,
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)

    _ensure_owner_if_exists(inst, user)

    staff = Staff(**dto.model_dump(), institution_id=institution_id)
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


@router.get("/{institution_id}/staff", response_model=list[Staff])
def list_staff(
    institution_id: int,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_db_session),
):
    if hasattr(Institution, "owner_id"):
        inst = session.get(Institution, institution_id)
        if not inst:
            raise HTTPException(status_code=404, detail=INSTITUTION_NOT_FOUND)
        _ensure_owner_if_exists(inst, user)

    q = select(Staff).where(Staff.institution_id == institution_id)
    return session.exec(q).all()
