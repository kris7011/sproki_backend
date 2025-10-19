from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.auth import require_role, User
from app.models_institution import Institution, Child, Staff

router = APIRouter(prefix="/leader", tags=["leader"])


def get_session() -> Session:
    from app.db import get_session as _gs
    return _gs()


@router.get("/dashboard")
async def dashboard(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_session),
):
    inst_count = session.exec(select(Institution)).all()
    child_count = session.exec(select(Child)).all()
    staff_count = session.exec(select(Staff)).all()
    return {
        "institutions": len(inst_count),
        "children": len(child_count),
        "staff": len(staff_count),
    }
