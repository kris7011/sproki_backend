# === FILE: app/routers/leader.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy import func

from app.auth import require_role, User
from app.models_institution import Institution, Child, Staff
# <-- brug generator-dependency direkte
from app.db import get_session as get_db_session

router = APIRouter(prefix="/leader", tags=["leader"])


@router.get("/dashboard")
async def dashboard(
    user: User = Depends(require_role(["leader"])),
    session: Session = Depends(get_db_session),
):
    # Mere effektivt: brug COUNT(*) i DB i stedet for at hente alle rækker
    inst_count = session.exec(
        select(func.count()).select_from(Institution)).one()
    child_count = session.exec(select(func.count()).select_from(Child)).one()
    staff_count = session.exec(select(func.count()).select_from(Staff)).one()

    return {
        "institutions": int(inst_count),
        "children": int(child_count),
        "staff": int(staff_count),
    }
