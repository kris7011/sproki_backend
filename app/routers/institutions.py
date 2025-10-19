# === FILE: app/routers/institutions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_role, User
from app.models_institution import (
    Institution,
    InstitutionCreate,
    Staff,
    StaffCreate,
)

router = APIRouter(prefix="/institutions", tags=["institutions"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.post("/", response_model=Institution)
def create_institution(
    dto: InstitutionCreate,
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    inst = Institution(**dto.dict())
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


@router.get("/mine", response_model=list[Institution])
def list_my_institutions(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    # NOTE: Hvis vi senere tilføjer owner_id, kan vi filtrere her.
    result = session.exec(select(Institution)).all()
    return result


@router.post("/{institution_id}/staff", response_model=Staff)
def add_staff(
    institution_id: int,
    dto: StaffCreate,
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    inst = session.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    staff = Staff(**dto.dict(), institution_id=institution_id)
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


@router.get("/{institution_id}/staff", response_model=list[Staff])
def list_staff(
    institution_id: int,
    user: User = Depends(require_role(["leader", "staff"])),
    session: Session = Depends(get_session),
):
    q = select(Staff).where(Staff.institution_id == institution_id)
    return session.exec(q).all()
